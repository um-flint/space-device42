#!/usr/bin/python

import requests
import json
import base64
import ConfigParser

def processDevice(device):
    sysdata = {}
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

def main():
    config = ConfigParser.ConfigParser()
    config.readfp(open('space-device42.cfg'))
    spaceusername = config.get('JunosSpace','username')
    spacepassword = config.get('JunosSpace','password')
    spaceUri = config.get('JunosSpace','baseUri')
    d42username = config.get('device42','username')
    d42password = config.get('device42','password')
    device42Uri = config.get('device42','baseUri')

    spaceheaders = {'Authorization': 'Basic ' + base64.b64encode(spaceusername+ ':' + spacepassword)}

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


    # "I don't want to live on this planet anymore" - Professor Hubert Farnsworth, after dealing with Accept headers in Junos Space
    #Putting this outside the loop before we look up contract info as theres no need to do it hundreds of times
    spaceheaders.update({'Accept': 'application/vnd.juniper.servicenow.device-management.device-contracts+json;version=1'})

    for device in devices:
        #print 'Processing switch named ' + device['name']
        sysdata = processDevice(device)
        #print 'Attempting to add to Device42'
        r = requests.post(device42Uri+'/api/device/',data=sysdata,headers=dsheaders)
        #print r
        #print r.text
        
        #Add the management IP for the switch
        ipdata = {}
        ipdata.update({'ipaddress': device['ipAddr']})
        #look up the device by serial number incase it already exists with a different name
        r=requests.get(device42Uri+'/api/1.0/devices/serial/'+sysdata['serial_no']+'/',headers=dsheaders)
        existingname = r.json()['name']
        ipdata.update({'device': existingname})
        #print 'Attempting to add IP info to Device42'
        r=requests.post(device42Uri+'/api/1.0/ips/',data=ipdata,headers=dsheaders)
        #print r
        #print r.text

        serviceNowDevice = filter(lambda x: x['serialNumber'] == device['serialNumber'], serviceNowDevices)
        if serviceNowDevice is not []:
            deviceContract=requests.get(spaceUri+'/api/juniper/servicenow/device-management/devices/' + serviceNowDevice[0]['@key']+ '/viewContractInformation',headers=spaceheaders,verify=False)
            if deviceContract.status_code == 200:
                print json.dumps(deviceContract.json()['deviceContracts']['deviceContract'], indent=4, sort_keys=True)


    return

if __name__ == '__main__': 
    main()
