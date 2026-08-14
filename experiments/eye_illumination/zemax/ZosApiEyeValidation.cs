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
        public double FocalLengthMm;
        public double AxialLengthMm;
        public double ImageIndex;
        public double TargetDiameterMm;
        public double PupilDiameterMm;
        public double SourceDistanceMm;
    }

    private sealed class CaseSolution
    {
        public double ReducedRetinaDistanceMm;
        public double SourceCoefficient;
        public double PupilCoefficient;
        public double GeometricSourceDiameterMm;
        public double ConservativeSourceDiameterMm;
        public double ExpectedMinYmm;
        public double ExpectedMaxYmm;
    }

    public static int Main()
    {
        string installDir = Environment.GetEnvironmentVariable("ZEMAX_OPTICSTUDIO_DIR");
        string outputDir = Environment.GetEnvironmentVariable("EYE_EXPERIMENT_ZEMAX_DIR");
        if (String.IsNullOrWhiteSpace(installDir) || !Directory.Exists(installDir)) return 2;
        if (String.IsNullOrWhiteSpace(outputDir) || !Directory.Exists(outputDir)) return 3;

        IZOSAPI_Application application = null;
        try
        {
            if (!ZOSAPI_Initializer.Initialize(installDir))
                throw new InvalidOperationException("Unable to initialize OpticStudio.");
            application = new ZOSAPI_Connection().CreateNewApplication();
            if (application == null || !application.IsValidLicenseForAPI)
                throw new InvalidOperationException("A valid ZOS-API license is required.");

            const double n = 1.336;
            var cases = new List<ValidationCase>
            {
                new ValidationCase { Id="chick_fixed_f7p5_d60_p3p5", FocalLengthMm=7.5, AxialLengthMm=11.7, ImageIndex=n, TargetDiameterMm=3.0, PupilDiameterMm=3.5, SourceDistanceMm=1000.0/60.0 },
                new ValidationCase { Id="chick_fixed_f8p5_d120_p2", FocalLengthMm=8.5, AxialLengthMm=11.7, ImageIndex=n, TargetDiameterMm=3.0, PupilDiameterMm=2.0, SourceDistanceMm=1000.0/120.0 },
                new ValidationCase { Id="child_fixed_f13p5_d60_p5", FocalLengthMm=13.5, AxialLengthMm=23.0, ImageIndex=n, TargetDiameterMm=6.0, PupilDiameterMm=5.0, SourceDistanceMm=1000.0/60.0 },
                new ValidationCase { Id="child_fixed_f16p7_d120_p2", FocalLengthMm=16.7, AxialLengthMm=23.0, ImageIndex=n, TargetDiameterMm=6.0, PupilDiameterMm=2.0, SourceDistanceMm=1000.0/120.0 },
                new ValidationCase { Id="adult_fixed_f12p8_d60_p5", FocalLengthMm=12.8, AxialLengthMm=23.6, ImageIndex=n, TargetDiameterMm=6.0, PupilDiameterMm=5.0, SourceDistanceMm=1000.0/60.0 },
                new ValidationCase { Id="adult_fixed_f16p7_d120_p2", FocalLengthMm=16.7, AxialLengthMm=23.6, ImageIndex=n, TargetDiameterMm=6.0, PupilDiameterMm=2.0, SourceDistanceMm=1000.0/120.0 }
            };

            string csvPath = Path.Combine(outputDir, "zosapi_validation.csv");
            using (var writer = new StreamWriter(csvPath, false))
            {
                writer.WriteLine("case_id,opticstudio_version,api_license_valid,source_distance_mm,pupil_diameter_mm,fixed_focal_length_mm,fixed_eye_power_D,axial_length_mm,image_index,reduced_retina_distance_mm,target_radius_mm,source_mapping_coefficient,pupil_mapping_coefficient,geometric_min_source_diameter_mm,conservative_source_diameter_mm,expected_min_y_mm,observed_min_y_mm,expected_max_y_mm,observed_max_y_mm,bound_error_um,valid_rays,zos_file");
                foreach (ValidationCase item in cases) RunCase(application, outputDir, writer, item, Solve(item));
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
        double t = item.AxialLengthMm / item.ImageIndex;
        double s = item.SourceDistanceMm;
        double mSource = -t / s;
        double mPupil = 1.0 + t / s - t / item.FocalLengthMm;
        double targetRadius = item.TargetDiameterMm / 2.0;
        double pupilRadius = item.PupilDiameterMm / 2.0;
        double pupilBlur = Math.Abs(mPupil) * pupilRadius;
        double sourceScale = Math.Abs(mSource);
        double geometricRadius = Math.Max(0.0, targetRadius - pupilBlur) / sourceScale;
        double conservativeRadius = (targetRadius + pupilBlur) / sourceScale;
        double[] ys = new double[4];
        int index = 0;
        foreach (double hy in new double[] { -1.0, 1.0 })
            foreach (double py in new double[] { -0.99, 0.99 })
                ys[index++] = mSource * hy * conservativeRadius + mPupil * py * pupilRadius;
        Array.Sort(ys);
        return new CaseSolution {
            ReducedRetinaDistanceMm=t,
            SourceCoefficient=mSource,
            PupilCoefficient=mPupil,
            GeometricSourceDiameterMm=2.0*geometricRadius,
            ConservativeSourceDiameterMm=2.0*conservativeRadius,
            ExpectedMinYmm=ys[0], ExpectedMaxYmm=ys[ys.Length-1]
        };
    }

    private static void RunCase(IZOSAPI_Application application, string outputDir, StreamWriter writer, ValidationCase item, CaseSolution solution)
    {
        IOpticalSystem system = application.PrimarySystem;
        system.New(false);
        system.SystemData.Aperture.ApertureValue = item.PupilDiameterMm;
        system.SystemData.Fields.SetFieldType(ZOSAPI.SystemData.FieldType.ObjectHeight);
        ZOSAPI.SystemData.IField field = system.SystemData.Fields.GetField(1);
        field.X = 0.0;
        field.Y = solution.ConservativeSourceDiameterMm / 2.0;
        system.SystemData.Wavelengths.GetWavelength(1).Wavelength = 0.650;

        ILDERow objectSurface = system.LDE.GetSurfaceAt(0);
        ILDERow eyeSurface = system.LDE.GetSurfaceAt(1);
        objectSurface.Thickness = item.SourceDistanceMm;
        ConfigureParaxial(eyeSurface, item.FocalLengthMm);
        eyeSurface.IsStop = true;
        eyeSurface.Thickness = solution.ReducedRetinaDistanceMm;
        eyeSurface.SemiDiameter = item.PupilDiameterMm / 2.0;

        string zosPath = Path.Combine(outputDir, item.Id + ".zos");
        if (File.Exists(zosPath)) File.Delete(zosPath);
        system.SaveAs(zosPath);

        var raytrace = system.Tools.OpenBatchRayTrace();
        int nsur = system.LDE.NumberOfSurfaces;
        var data = raytrace.CreateNormUnpol(4, ZOSAPI.Tools.RayTrace.RaysType.Real, nsur);
        foreach (double hy in new double[] { -1.0, 1.0 })
            foreach (double py in new double[] { -0.99, 0.99 })
                data.AddRay(1, 0.0, hy, 0.0, py, ZOSAPI.Tools.RayTrace.OPDMode.None);
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
        if (valid != 4) throw new InvalidOperationException("Expected four valid rays for " + item.Id);
        ys.Sort();
        double errorUm = 1000.0 * Math.Max(Math.Abs(ys[0] - solution.ExpectedMinYmm), Math.Abs(ys[ys.Count-1] - solution.ExpectedMaxYmm));

        writer.WriteLine(String.Join(",", new string[] {
            item.Id,
            application.ZOSMajorVersion + "." + application.ZOSMinorVersion + "." + application.ZOSSPVersion,
            application.IsValidLicenseForAPI.ToString().ToLowerInvariant(),
            F(item.SourceDistanceMm), F(item.PupilDiameterMm), F(item.FocalLengthMm), F(1000.0/item.FocalLengthMm),
            F(item.AxialLengthMm), F(item.ImageIndex), F(solution.ReducedRetinaDistanceMm), F(item.TargetDiameterMm/2.0),
            F(solution.SourceCoefficient), F(solution.PupilCoefficient), F(solution.GeometricSourceDiameterMm), F(solution.ConservativeSourceDiameterMm),
            F(solution.ExpectedMinYmm), F(ys[0]), F(solution.ExpectedMaxYmm), F(ys[ys.Count-1]), F(errorUm),
            valid.ToString(CultureInfo.InvariantCulture), Path.GetFileName(zosPath)
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
