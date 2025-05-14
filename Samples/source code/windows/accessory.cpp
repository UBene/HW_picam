#include "stdio.h"
#include "picam_accessory.h"

#include <iostream>
#include <string>
#include <sstream>

using namespace std;
/******************************************************************************
* Show any error codes
******************************************************************************/
bool ShowErrorCode(pichar *functionName, PicamError error)
{
    if (error != PicamError_None)
    {
        const pichar *pError;
        Picam_GetEnumerationString(PicamEnumeratedType_Error, error, &pError);
        printf("%s: Returned Error %s \n", functionName, pError);
        Picam_DestroyString(pError);
        return false;
    }
    return true;
}
/******************************************************************************
* Show Accessory Information
******************************************************************************/
void ShowAccessoryInformation(piint index, PicamAccessoryID pAcc)
{
    /* Show the device name and the serial number */    
    switch (pAcc.model)
    {
        case PicamModel_FergieAEL:
            printf("%i. Fergie AEL => S/N %s \n", (int)index, pAcc.serial_number);
            break;

        case PicamModel_FergieQTH:
            printf("%i. Fergie QTH => S/N %s \n", (int)index, pAcc.serial_number);
            break;

        case PicamModel_IntellicalSwirQTH:
            printf("%i. SWIR QTH => S/N %s \n", (int)index, pAcc.serial_number);
            break;
            
        case PicamModel_FergieLaser785:
        case PicamModel_FergieLaser532:
            printf("%i. Fergie Laser => S/N %s \n", (int)index, pAcc.serial_number);
            break;
    }  

    /* Show the firmware details */
    const PicamFirmwareDetail *pFw;
    piint fwCount = 0; 
    if (PicamAccessory_GetFirmwareDetails(&pAcc, &pFw, &fwCount) == PicamError_None)
    {
        for (int fwIdx = 0; fwIdx < fwCount; fwIdx++)
            printf("\tFirmware: %s Details: %s \n", pFw[fwIdx].name, pFw[fwIdx].detail);

        /* Clean up the memory associated with firmware */
        Picam_DestroyFirmwareDetails(pFw);
    }
}
/******************************************************************************
* Test Mode(s)
******************************************************************************/
void TestModes(PicamHandle handle, 
               PicamParameter parameter, 
               piint mode1, 
               piint mode2, 
               const pichar* prefix)
{
    piint originalValue;

    const pichar *parameterString; 
    Picam_GetEnumerationString(PicamEnumeratedType_Parameter, parameter, &parameterString);    

    /* Read value back for mode1 */    
    if (ShowErrorCode("Picam_GetParameterIntegerValue",
        Picam_GetParameterIntegerValue(handle, parameter, &originalValue)))
    {
        /* Set value to mode1 and display both values */
        if (ShowErrorCode("Picam_SetParameterIntegerValue",
            Picam_SetParameterIntegerValue(handle, parameter, mode1)))
        {
            PicamEnumeratedType type;
            Picam_GetParameterEnumeratedType(handle, parameter, &type);
            
            const pichar *beforeString, *afterString;
            Picam_GetEnumerationString(type, originalValue, &beforeString);
            Picam_GetEnumerationString(type, mode1, &afterString);
            printf("%s: %s value changed from %s to %s \n", prefix, parameterString, beforeString, afterString); 
            Picam_DestroyString(beforeString);
            Picam_DestroyString(afterString);
        }
    }
    /* Read value back for mode2 */    
    if (ShowErrorCode("Picam_GetParameterIntegerValue",
        Picam_GetParameterIntegerValue(handle, parameter, &originalValue)))
    {
        /* Set value to mode2 and display both values */
        if (ShowErrorCode("Picam_SetParameterIntegerValue",
            Picam_SetParameterIntegerValue(handle, parameter, mode2)))
        {
            PicamEnumeratedType type;
            Picam_GetParameterEnumeratedType(handle, parameter, &type);

            const pichar *beforeString, *afterString;
            Picam_GetEnumerationString(type, originalValue, &beforeString);
            Picam_GetEnumerationString(type, mode2, &afterString);
            printf("%s: %s value changed from %s to %s \n", prefix, parameterString, beforeString, afterString); 
            Picam_DestroyString(beforeString);
            Picam_DestroyString(afterString);
        }
    }   

    /* Cleanup the parameter name string */
    Picam_DestroyString(parameterString);
}
/******************************************************************************
* Test Qth Lamp
******************************************************************************/
void TestQthLamp(PicamHandle handle)
{
    /* Test toggling lamp on / off */
    TestModes(handle, 
              PicamParameter_LightSource, 
              PicamLightSource_Disabled, 
              PicamLightSource_Qth, 
              "Qth");

    /* Get the time the device has been on since manufacture */
    piflt onTimeSeconds; 
    if (ShowErrorCode("Picam_GetParameterFloatingPointValue", 
                      Picam_GetParameterFloatingPointValue(handle, PicamParameter_Age, &onTimeSeconds)))
        printf("Qth: Lifetime %f \n", (float)onTimeSeconds);
     
    /* Get the expected shelf life of the device */
    piflt lifeSeconds; 
    if (ShowErrorCode("Picam_GetParameterFloatingPointValue", 
                      Picam_GetParameterFloatingPointValue(handle, PicamParameter_LifeExpectancy, &lifeSeconds)))
        printf("Qth: Life expectancy %f \n", lifeSeconds);

    /* Get the light source status */
    piint status; 
    if (ShowErrorCode("Picam_SetParameterIntegerValue", 
                      Picam_GetParameterIntegerValue(handle, 
                                                     PicamParameter_LightSourceStatus, 
                                                     &status)))
        (status == PicamLightSourceStatus_Unstable) ? 
            printf("Qth: Source Unstable \n") : printf("Qth: Source Stable \n");        

    /* Get the reference data out of the lamp */
    const PicamCalibration *pCalibrations;
    if (ShowErrorCode("PicamAccessory_GetLightSourceReference", 
                      PicamAccessory_GetLightSourceReference(handle, 
                                                             &pCalibrations)))
    {
        /* show the count */
        printf("Qth: Calibration point count %d \n", (int)pCalibrations->point_count);

        /* show the first point */
        printf("Qth: First calibration X = %f, Y = %f \n", 
                (float)(pCalibrations->point_array[0].x), 
                (float)(pCalibrations->point_array[0].y));

        /* show the last point */
        printf("Qth: Last calibration X = %f, Y = %f \n", 
                (float)(pCalibrations->point_array[pCalibrations->point_count-1].x), 
                (float)(pCalibrations->point_array[pCalibrations->point_count-1].y));

        /* Free the calibration object */
        Picam_DestroyCalibrations(pCalibrations);
    }    
    
}
/******************************************************************************
* Test AE Lamp
******************************************************************************/
void TestAELamp(PicamHandle handle)
{
    /* Test toggling lamp on / off */
    TestModes(handle, 
              PicamParameter_LightSource,
              PicamLightSource_Disabled, 
              PicamLightSource_Hg,
              "AtomicEmissions");    
}
/******************************************************************************
* Test Laser Power
******************************************************************************/
void TestLaserPower(PicamHandle handle)
{
     /* Set the laser power to 50x */
    ShowErrorCode("Picam_SetParameterFloatingPointValue",
                  Picam_SetParameterFloatingPointValue(handle, 
                                                       PicamParameter_LaserPower, 
                                                       50));
    /* Confirm the laser power */
    piflt laserPower;
    ShowErrorCode("Picam_GetParameterFloatingPointValue", 
                  Picam_GetParameterFloatingPointValue(handle, 
                                                       PicamParameter_LaserPower, 
                                                       &laserPower));
     printf("Laser: Current Power %f \n", (float)laserPower);
}
/******************************************************************************
* Test Laser
******************************************************************************/
void TestLaserModes(PicamHandle handle)
{
    /* Test toggling laser on / off */    
    TestModes(handle, 
                PicamParameter_LaserOutputMode,
                PicamLaserOutputMode_ContinuousWave, 
                PicamLaserOutputMode_Disabled,
                "Laser");            
}
/******************************************************************************
* Test Device 
******************************************************************************/
void TestDevice(const PicamAccessoryID &pAcc)
{
    pibln connected     = false;
    pibln openElsewhere = false;

    /* see if the device is connected */
    PicamError error 
        = PicamAccessory_IsAccessoryIDConnected(&pAcc, &connected);
    ShowErrorCode("PicamAccessory_IsAccessoryIDConnected", error);

    /* see if the device is open somewhere else */
    error 
        = PicamAccessory_IsAccessoryIDOpenElsewhere(&pAcc, &openElsewhere);
    ShowErrorCode("PicamAccessory_IsAccessoryIDOpenElsewhere", error);

    /* If we are connected and not open somewhere else then test the accessory */
    if (connected && !openElsewhere)
    {
        PicamHandle hAcc; 
        error = PicamAccessory_OpenAccessory(&pAcc, &hAcc);
        ShowErrorCode("PicamAccessory_OpenAccessory", error);

        if (error == PicamError_None)
        {            
            switch (pAcc.model)
            {
                case PicamModel_FergieAEL: 
                    TestAELamp(hAcc);
                    break;

                case PicamModel_FergieQTH:              
                case PicamModel_IntellicalSwirQTH:
                    TestQthLamp(hAcc);
                    break;

                case PicamModel_FergieLaser785:            
                    TestLaserModes(hAcc);
                    TestLaserPower(hAcc);
                    break;

                /* 532 laser only has power and nothing else */
                case PicamModel_FergieLaser532:
                    TestLaserPower(hAcc); 
                    break;
            }
            
            /* Close the accessory */
            error = PicamAccessory_CloseAccessory(hAcc);
            ShowErrorCode("PicamAccessory_CloseAccessory", error);
        }
    }
    else
        printf("Device is open elsewhere or no longer connected! \n");
}
/******************************************************************************
* Process input key
******************************************************************************/
pibool ProcessKeyStroke(const PicamAccessoryID *ptrAccessories,
                        piint number,                        
                        const std::string& inputString)
{    
    /* X or x means we are done */
    if ((strcmp(inputString.c_str(), "X") == 0) || 
        (strcmp(inputString.c_str(), "x") == 0))    
        return true;

    /* Lets test one of the accessories */    
    int devIdx = atoi(inputString.c_str()) - 1;

    if (devIdx >= 0 && devIdx < number)
        TestDevice(ptrAccessories[devIdx]);
    else    
        printf("Invalid device selection! \n");

    /* Continue */
    return false;
}
/******************************************************************************
*  Demonstrate Accessory Devices
******************************************************************************/
int main()
{   
    const PicamAccessoryID *ptrAccessories;
    piint numberAccessories = 0; 
    
    /* Initialize the library */
    Picam_InitializeLibrary();

    /* See what is installed (allocates ptrAccessories memory) */
    PicamError error 
        = PicamAccessory_GetAvailableAccessoryIDs(&ptrAccessories, &numberAccessories);

    if (error == PicamError_None)
    {
        /* Show the detected accessories */
        for (int i=0; i<numberAccessories; i++)
            ShowAccessoryInformation(i+1, ptrAccessories[i]);

        std::string inputString;
        do 
        {           
            printf("Choose Accessory to test or x to exit followed by a carriage return. \n");
            cin >> inputString;
            
        } while (!ProcessKeyStroke(ptrAccessories, numberAccessories, inputString));

        /* Clean up the accessory array (frees memory) */
        PicamAccessory_DestroyAccessoryIDs(ptrAccessories);
    }
    else             
        ShowErrorCode("PicamAccessory_GetAvailableAccessoryIDs", error);    
          
    /* Free the library */
    Picam_UninitializeLibrary();
}
