using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using ZOSAPI;
using ZOSAPI.Editors.LDE;
using ZOSAPI_NetHelper;

public static class ZosApiEyeValidation
{
    private sealed class ValidationCase
    {
        public string Id;
        public double F0Mm;
        public double TargetDiameterMm;
        public double PupilDiameterMm;
        public double SourceDistanceMm;
        public double ExternalPowerD;
        public double VertexDistanceMm;
        public bool Accommodated;
    }

    private sealed class CaseSolution
    {
        public double AccommodationD;
        public double EyePowerD;
        public double SourceDiameterMm;
    }

    public static int Main()
    {
        string installDir = Environment.GetEnvironmentVariable("ZEMAX_OPTICSTUDIO_DIR");
        if (String.IsNullOrWhiteSpace(installDir) || !Directory.Exists(installDir))
        {
            Console.Error.WriteLine("ZEMAX_OPTICSTUDIO_DIR must name the OpticStudio installation directory.");
            return 2;
        }
        string outputDir = Environment.GetEnvironmentVariable("EYE_EXPERIMENT_ZEMAX_DIR");
        if (String.IsNullOrWhiteSpace(outputDir) || !Directory.Exists(outputDir))
        {
            Console.Error.WriteLine("EYE_EXPERIMENT_ZEMAX_DIR must name an existing directory.");
            return 3;
        }

        IZOSAPI_Application application = null;
        try
        {
            if (!ZOSAPI_Initializer.Initialize(installDir))
                throw new InvalidOperationException("Unable to initialize OpticStudio from " + installDir + ".");
            IZOSAPI_Connection connection = new ZOSAPI_Connection();
            application = connection.CreateNewApplication();
            if (application == null || !application.IsValidLicenseForAPI)
                throw new InvalidOperationException("A valid ZOS-API license is required.");

            var cases = new List<ValidationCase>
            {
                new ValidationCase { Id="chick_d10", F0Mm=8.4, TargetDiameterMm=3.0, PupilDiameterMm=3.5, SourceDistanceMm=100, ExternalPowerD=0, VertexDistanceMm=5, Accommodated=true },
                new ValidationCase { Id="child_d10", F0Mm=16.7, TargetDiameterMm=6.0, PupilDiameterMm=5.0, SourceDistanceMm=100, ExternalPowerD=0, VertexDistanceMm=12, Accommodated=true },
                new ValidationCase { Id="adult_d10", F0Mm=16.7, TargetDiameterMm=6.0, PupilDiameterMm=5.0, SourceDistanceMm=100, ExternalPowerD=0, VertexDistanceMm=12, Accommodated=true },
                new ValidationCase { Id="adult_d5_ext_m5", F0Mm=16.7, TargetDiameterMm=6.0, PupilDiameterMm=5.0, SourceDistanceMm=200, ExternalPowerD=-5, VertexDistanceMm=12, Accommodated=true },
                new ValidationCase { Id="adult_d10_ext_m10", F0Mm=16.7, TargetDiameterMm=6.0, PupilDiameterMm=5.0, SourceDistanceMm=100, ExternalPowerD=-10, VertexDistanceMm=12, Accommodated=true },
                new ValidationCase { Id="adult_d10_unaccommodated", F0Mm=16.7, TargetDiameterMm=6.0, PupilDiameterMm=5.0, SourceDistanceMm=100, ExternalPowerD=0, VertexDistanceMm=12, Accommodated=false }
            };

            string csvPath = Path.Combine(outputDir, "zosapi_validation.csv");
            using (var writer = new StreamWriter(csvPath, false))
            {
                writer.WriteLine("case_id,opticstudio_version,api_license_valid,accommodated,source_distance_mm,external_lens_D,vertex_distance_mm,pupil_diameter_mm,eye_focal_length_mm,eye_power_D,accommodation_D,source_diameter_mm,target_radius_mm,mean_image_y_mm,min_image_y_mm,max_image_y_mm,rms_spread_um,valid_rays,zos_file");
                foreach (ValidationCase item in cases)
                {
                    CaseSolution solution = Solve(item);
                    RunCase(application, outputDir, writer, item, solution);
                }
            }
            Console.WriteLine("ZOSAPI_VALIDATION_CSV=" + csvPath);
            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("ERROR_TYPE=" + ex.GetType().FullName);
            Console.Error.WriteLine("ERROR_MESSAGE=" + ex.Message);
            Console.Error.WriteLine(ex.StackTrace);
            return 1;
        }
        finally
        {
            if (application != null) application.CloseApplication();
        }
    }

    private static CaseSolution Solve(ValidationCase item)
    {
        double L = item.SourceDistanceMm / 1000.0;
        double d = item.VertexDistanceMm / 1000.0;
        double p = item.ExternalPowerD;
        double b = L - d * p * (L - d);
        double matrixD = 1.0 - p * (L - d);
        double accommodation = matrixD / b;
        double baselinePower = 1000.0 / item.F0Mm;
        double eyePower = item.Accommodated ? baselinePower + accommodation : baselinePower;
        double reducedRetinaDistance = 1.0 / baselinePower;
        double focusedMagnification = reducedRetinaDistance / b;
        double sourceDiameter = item.TargetDiameterMm / Math.Abs(focusedMagnification);
        return new CaseSolution { AccommodationD=accommodation, EyePowerD=eyePower, SourceDiameterMm=sourceDiameter };
    }

    private static void RunCase(IZOSAPI_Application application, string outputDir, StreamWriter writer, ValidationCase item, CaseSolution solution)
    {
        IOpticalSystem system = application.PrimarySystem;
        system.New(false);
        system.SystemData.Aperture.ApertureValue = item.PupilDiameterMm;
        system.SystemData.Fields.SetFieldType(ZOSAPI.SystemData.FieldType.ObjectHeight);
        ZOSAPI.SystemData.IField field = system.SystemData.Fields.GetField(1);
        field.X = 0.0;
        field.Y = solution.SourceDiameterMm / 2.0;
        system.SystemData.Wavelengths.GetWavelength(1).Wavelength = 0.650;

        ILDERow objectSurface = system.LDE.GetSurfaceAt(0);
        ILDERow eyeSurface;
        if (Math.Abs(item.ExternalPowerD) > 1e-12)
        {
            system.LDE.InsertNewSurfaceAt(2);
            ILDERow externalSurface = system.LDE.GetSurfaceAt(1);
            eyeSurface = system.LDE.GetSurfaceAt(2);
            objectSurface.Thickness = item.SourceDistanceMm - item.VertexDistanceMm;
            ConfigureParaxial(externalSurface, 1000.0 / item.ExternalPowerD);
            externalSurface.Thickness = item.VertexDistanceMm;
            ConfigureParaxial(eyeSurface, 1000.0 / solution.EyePowerD);
        }
        else
        {
            eyeSurface = system.LDE.GetSurfaceAt(1);
            objectSurface.Thickness = item.SourceDistanceMm;
            ConfigureParaxial(eyeSurface, 1000.0 / solution.EyePowerD);
        }
        eyeSurface.IsStop = true;
        eyeSurface.Thickness = item.F0Mm;
        eyeSurface.SemiDiameter = item.PupilDiameterMm / 2.0;

        string zosPath = Path.Combine(outputDir, item.Id + ".zos");
        if (File.Exists(zosPath)) File.Delete(zosPath);
        system.SaveAs(zosPath);

        var raytrace = system.Tools.OpenBatchRayTrace();
        int nsur = system.LDE.NumberOfSurfaces;
        double[] pupilY = new double[] { -0.99, -0.5, 0.0, 0.5, 0.99 };
        var data = raytrace.CreateNormUnpol(pupilY.Length, ZOSAPI.Tools.RayTrace.RaysType.Real, nsur);
        foreach (double py in pupilY) data.AddRay(1, 0.0, 1.0, 0.0, py, ZOSAPI.Tools.RayTrace.OPDMode.None);
        raytrace.RunAndWaitForCompletion();
        data.StartReadingResults();

        int rayNumber, errorCode, vignetteCode, valid = 0;
        double x, y, z, l, m, n, l2, m2, n2, opd, intensity;
        var ys = new List<double>();
        bool success = data.ReadNextResult(out rayNumber, out errorCode, out vignetteCode, out x, out y, out z, out l, out m, out n, out l2, out m2, out n2, out opd, out intensity);
        while (success)
        {
            if (errorCode == 0 && vignetteCode == 0) { ys.Add(y); valid++; }
            success = data.ReadNextResult(out rayNumber, out errorCode, out vignetteCode, out x, out y, out z, out l, out m, out n, out l2, out m2, out n2, out opd, out intensity);
        }
        raytrace.Close();
        if (valid == 0) throw new InvalidOperationException("No valid rays for " + item.Id);

        double mean = 0.0;
        foreach (double value in ys) mean += value;
        mean /= ys.Count;
        double sumSquares = 0.0;
        foreach (double value in ys) sumSquares += (value - mean) * (value - mean);
        double rmsUm = 1000.0 * Math.Sqrt(sumSquares / ys.Count);
        ys.Sort();

        writer.WriteLine(String.Join(",", new string[] {
            item.Id,
            application.ZOSMajorVersion + "." + application.ZOSMinorVersion + "." + application.ZOSSPVersion,
            application.IsValidLicenseForAPI.ToString().ToLowerInvariant(),
            item.Accommodated.ToString().ToLowerInvariant(),
            F(item.SourceDistanceMm), F(item.ExternalPowerD), F(item.VertexDistanceMm), F(item.PupilDiameterMm),
            F(1000.0 / solution.EyePowerD), F(solution.EyePowerD), F(solution.AccommodationD), F(solution.SourceDiameterMm),
            F(item.TargetDiameterMm / 2.0), F(mean), F(ys[0]), F(ys[ys.Count - 1]), F(rmsUm), valid.ToString(CultureInfo.InvariantCulture),
            Path.GetFileName(zosPath)
        }));
        writer.Flush();
    }

    private static void ConfigureParaxial(ILDERow surface, double focalLengthMm)
    {
        ISurfaceTypeSettings settings = surface.GetSurfaceTypeSettings(SurfaceType.Paraxial);
        surface.ChangeType(settings);
        ISurfaceParaxial data = surface.SurfaceData as ISurfaceParaxial;
        if (data == null) throw new InvalidOperationException("Unable to obtain paraxial surface data.");
        data.FocalLength = focalLengthMm;
    }

    private static string F(double value) { return value.ToString("G17", CultureInfo.InvariantCulture); }
}
