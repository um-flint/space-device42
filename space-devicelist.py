#!/usr/bin/python

#This code prints out a list of all the devices in Junos Space
#Useful for understanding what data is in Junos Space or debugging

import requests
import json
import base64
import ConfigParser

def main():
    #Parse the config file
    config = ConfigParser.ConfigParser()
    config.readfp(open('space-device42.cfg'))
    spaceusername = config.get('JunosSpace','username')
    spacepassword = config.get('JunosSpace','password')
    spaceUri = config.get('JunosSpace','baseUri')

    #Default headers for Junos Space
    spaceheaders = {'Authorization': 'Basic ' + base64.b64encode(spaceusername+ ':' + spacepassword)}

    #Get device info
    #   Why can't you just use 'application/json' Juniper?
    spaceheaders.update({'Accept': 'application/vnd.net.juniper.space.device-management.devices+json;version=1'})
    r=requests.get(spaceUri+'/api/space/device-management/devices',headers=spaceheaders,verify=False)
    print r


    print 'Total devices listed:', len(r.json()['devices']['device'])
    print json.dumps(r.json(), indent=4, sort_keys=True)

    return

if __name__ == '__main__': 
    main()
