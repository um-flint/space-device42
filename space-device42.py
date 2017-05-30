#!/usr/bin/python

import requests
import json
import base64
import ConfigParser

# Parse the data about a device from Space and convert it to Device42 format
def processDevice(device):
    sysdata = {}
    
    #List of models that have card slots so consider them blade chassis in device42
    #Could change over time/be different across environments
    bladeHosts=['EX8208']
    
    sysdata.update({'name': device['name']})
    sysdata.update({'serial_no': device['serialNumber']})
    sysdata.update({'manufacturer': 'Juniper'})
    sysdata.update({'hardware': device['platform']})
    sysdata.update({'os': 'Junos OS'})
    sysdata.update({'osver': device['OSVersion']})
    sysdata.update({'is_it_switch': 'yes'})
    if device['platform'] in bladeHosts:
        sysdata.update({'is_it_blade_host': 'yes'})

    return sysdata

# Parse the data about a contract from Space and convert it to Device42 format
def processContract(deviceContract,serialNumber):
    contractdata = {}
    contractdata.update({'order_no': 'Juniper Care - ' + deviceContract['contractAgreementNumber']})
    contractdata.update({'line_type': 'Contract'})
    contractdata.update({'line_contract_type': 'Juniper Care'})
    contractdata.update({'line_service_type': deviceContract['contractSKU']})
    contractdata.update({'line_contract_id': deviceContract['contractAgreementNumber']})
    contractdata.update({'line_start_date': deviceContract['contractStartDate'].split()[0]})
    contractdata.update({'line_end_date': deviceContract['contractEndDate'].split()[0]})
    contractdata.update({'line_device_serial_nos': serialNumber})

    return contractdata

#Print OK if upload was sucessful - otherwise display response received
def processReturnCode(r):
    if r.status_code == 200:
        print '  OK'
    else:
        print '  Error,',r
        print ' ', r.text
    
    return

def main():
    #Parse the config file
    config = ConfigParser.ConfigParser()
    config.readfp(open('space-device42.cfg'))
    spaceusername = config.get('JunosSpace','username')
    spacepassword = config.get('JunosSpace','password')
    spaceUri = config.get('JunosSpace','baseUri')
    d42username = config.get('device42','username')
    d42password = config.get('device42','password')
    device42Uri = config.get('device42','baseUri')

    #Default headers for Junos Space
    spaceheaders = {'Authorization': 'Basic ' + base64.b64encode(spaceusername+ ':' + spacepassword)}

    #Default headers for Device42
    dsheaders = {'Authorization': 'Basic ' + base64.b64encode(d42username + ':' + d42password), 'Content-Type': 'application/x-www-form-urlencoded'}

    #Get device info
    #   Why can't you just use 'application/json' Juniper?
    spaceheaders.update({'Accept': 'application/vnd.net.juniper.space.device-management.devices+json;version=1'})
    r=requests.get(spaceUri+'/api/space/device-management/devices',headers=spaceheaders,verify=False)
    #If its not a Juniper device, we probably don't have many details on it so ignore it
    devices = [ x for x in r.json()['devices']['device'] if x['deviceFamily'].startswith('junos') ]

    #Get device info from ServiceNow (to allow warranty/contract lookup)
    #   Seriously, why Juniper?
    spaceheaders.update({'Accept': 'application/vnd.juniper.servicenow.device-management.devices+json;version=5'})
    r = requests.get(spaceUri+'/api/juniper/servicenow/device-management/devices', headers=spaceheaders, verify=False)
    #If we don't have a serial number for a device, then ignore it
    serviceNowDevices = [ x for x in r.json()['devices']['device'] if 'serialNumber' in x ]


    #Putting this outside the loop before we look up contract info as theres no need to do it hundreds of times
    # "I don't want to live on this planet anymore" - Professor Hubert Farnsworth, after dealing with Accept headers in Junos Space
    spaceheaders.update({'Accept': 'application/vnd.juniper.servicenow.device-management.device-contracts+json;version=1'})

    for device in devices:
        print 'Processing switch named', device['name']
        sysdata = processDevice(device)
        print ' Attempting to add hardware to Device42'
        r = requests.post(device42Uri+'/api/device/',data=sysdata,headers=dsheaders)
        processReturnCode(r)
        
        #Add the management IP for the switch
        ipdata = {}
        ipdata.update({'ipaddress': device['ipAddr']})
        #look up the device by serial number incase it already exists with a different name
        r=requests.get(device42Uri+'/api/1.0/devices/serial/'+sysdata['serial_no']+'/',headers=dsheaders)
        existingname = r.json()['name']
        ipdata.update({'device': existingname})
        print ' Attempting to add IP info to Device42'
        r=requests.post(device42Uri+'/api/1.0/ips/',data=ipdata,headers=dsheaders)
        processReturnCode(r)

        #Match the contracts up to the devices
        serviceNowDevice = filter(lambda x: x['serialNumber'] == device['serialNumber'], serviceNowDevices)
        if serviceNowDevice is not []:
            deviceContracts=requests.get(spaceUri+'/api/juniper/servicenow/device-management/devices/' + serviceNowDevice[0]['@key']+ '/viewContractInformation',headers=spaceheaders,verify=False)
            if deviceContracts.status_code == 200:
                if type(deviceContracts.json()['deviceContracts']['deviceContract']) is list:
                    for contract in deviceContracts.json()['deviceContracts']['deviceContract']:
                        contractdata = processContract(contract, sysdata['serial_no'])
                        print ' Attempting to add contract', contract['contractAgreementNumber'], 'to Device42'
                        #print json.dumps(contractdata, indent=4, sort_keys=True)
                        r = requests.post(device42Uri+'/api/1.0/purchases/',data=contractdata,headers=dsheaders)
                        processReturnCode(r)

                else:
                    contractdata = processContract(deviceContracts.json()['deviceContracts']['deviceContract'], sysdata['serial_no'])
                    print ' Attempting to add contract', deviceContracts.json()['deviceContracts']['deviceContract']['contractAgreementNumber'], 'to Device42'
                    #print json.dumps(contractdata, indent=4, sort_keys=True)
                    r = requests.post(device42Uri+'/api/1.0/purchases/',data=contractdata,headers=dsheaders)
                    processReturnCode(r)
        print

    return

if __name__ == '__main__': 
    main()
