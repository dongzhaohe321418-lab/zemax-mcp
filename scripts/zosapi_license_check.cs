using System;
using ZOSAPI;
using ZOSAPI_NetHelper;

public static class ZosApiLicenseCheck
{
    public static int Main()
    {
        string installDir = Environment.GetEnvironmentVariable("ZEMAX_OPTICSTUDIO_DIR");
        if (String.IsNullOrWhiteSpace(installDir) || !System.IO.Directory.Exists(installDir))
        {
            Console.Error.WriteLine("ZEMAX_OPTICSTUDIO_DIR must name the OpticStudio installation directory.");
            return 5;
        }
        IZOSAPI_Connection connection = null;
        IZOSAPI_Application application = null;
        try
        {
            if (!ZOSAPI_Initializer.Initialize(installDir))
            {
                Console.Error.WriteLine("INITIALIZATION_FAILED");
                return 2;
            }

            connection = new ZOSAPI_Connection();
            application = connection.CreateNewApplication();
            if (application == null)
            {
                Console.Error.WriteLine("APPLICATION_CREATION_FAILED");
                return 3;
            }

            Console.WriteLine("CONNECTED=true");
            Console.WriteLine("API_LICENSE_VALID=" + application.IsValidLicenseForAPI);
            Console.WriteLine("OPTICSTUDIO_VERSION=" + application.ZOSMajorVersion + "." + application.ZOSMinorVersion + "." + application.ZOSSPVersion);
            return application.IsValidLicenseForAPI ? 0 : 4;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("ERROR_TYPE=" + ex.GetType().FullName);
            Console.Error.WriteLine("ERROR_MESSAGE=" + ex.Message);
            return 1;
        }
        finally
        {
            if (application != null)
            {
                application.CloseApplication();
            }
            connection = null;
        }
    }
}
