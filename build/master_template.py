#/usr/bin/python env

from optparse import OptionParser
import json
from troposphere import Base64, Select, FindInMap, GetAtt, GetAZs, Join, Output
from troposphere import Parameter, Ref, Tags, Template
from troposphere.cloudformation import Init, Metadata, InitConfig, InitFiles, InitFile
# from troposphere.ec2 import VPC
# from troposphere.ec2 import InternetGateway
# from troposphere.ec2 import VPCGatewayAttachment
# from troposphere.ec2 import Subnet
# from troposphere.ec2 import RouteTable
# from troposphere.ec2 import Route
# from troposphere.ec2 import SubnetRouteTableAssociation
# from troposphere.ec2 import NetworkInterface
# from troposphere.ec2 import NetworkInterfaceProperty
# from troposphere.ec2 import EIPAssociation
# from troposphere.ec2 import EIP
# from troposphere.ec2 import PortRange
# from troposphere.ec2 import Instance
from troposphere.ec2 import *

def usage():
    print "OPTIONS:"
    print "     -s  stack  <network, security_groups, infra, full or existing>"
    print "     -a  <number of AvailabilityZones>"
    print "     -b  <number of BIG-IPs>"
    print "     -n  <number of NICs>. <1, 2, or 3>"
    print "     -l  license  <BYOL, hourly or BIG-IQ>"
    print "     -c  components <WAF, autoscale, etc.>"
    print "     -H  ha-type <standalone, same-az, across-az>"
    print "USAGE: "
    print " ex. " + sys.argv[0] + " -s network -n 1"
    print " ex. " + sys.argv[0] + " -s network -n 2 -a 2"
    print " ex. " + sys.argv[0] + " -s security_groups -n 2"
    print " ex. " + sys.argv[0] + " -s infra -n 2"
    print " ex. " + sys.argv[0] + " -s full -n 1 -l byol"
    print " ex. " + sys.argv[0] + " -s existing -n 2 -l bigiq"
    print " ex. " + sys.argv[0] + " -s existing -n 2 -l bigiq -c waf -H across-az"

def main():

    # RFE: Use Metadata / AWS::CloudFormation::Interface/  "ParameterGroups"
    # to clean up Presentation Layer

    PARAMETERS = {}
    MAPPINGS = {}
    RESOURCES = {}
    OUTPUTS = {}

    parser = OptionParser()
    parser.add_option("-s", "--stack", action="store", type="string", dest="stack", help="Stack: network, security_groups, infra, full or existing" )
    parser.add_option("-a", "--num-azs", action="store", type="int", dest="num_azs", default=1, help="Number of Availability Zones" )
    parser.add_option("-b", "--num-bigips", action="store", type="int", dest="num_bigips", default=1, help="Number of BIG-IPs" )
    parser.add_option("-n", "--nics", action="store", type="int", dest="num_nics", default=1, help="Number of NICs: 1,2 or 3")
    parser.add_option("-l", "--license", action="store", type="string", dest="license_type", default="hourly", help="Type of License: hourly, BYOL, or BIG-IQ" )
    parser.add_option("-c", "--components", action="store", type="string", dest="components", help="Comma seperated list of components: ex. WAF" )
    parser.add_option("-H", "--ha-type", action="store", type="string", dest="ha_type", default="standalone", help="HA Type: standalone, same-az, across-az" )

    (options, args) = parser.parse_args()


    num_nics = options.num_nics
    license_type = options.license_type
    stack = options.stack
    num_bigips = options.num_bigips
    ha_type = options.ha_type
    num_azs = options.num_azs

    # 1st BIG-IP will always be cluster seed
    CLUSTER_SEED = 1

    # May need to include AWS Creds for various deployments: cluster, auto-scale, etc.
    aws_creds = False 

    if ha_type == "same-az":
        num_azs = 1
        num_bigips = 2
        aws_creds = True

    # num AZs for Across AZ fixed for now. Limited to HA-Pairs
    if ha_type == "across-az":
        num_azs = 2
        num_bigips = 2
        aws_creds = True

    # Not Implemented. Fixed for now
    num_bigips_per_az = 1

    # Note, waf is only component right now
    components = {}
    if options.components:
        for component in options.components.split(','):
            components[component] = True

    network = False
    security_groups = False
    webserver = False
    bigip = False

    if stack == "network":
        network = True
        security_groups = False
        webserver = False
        bigip = False

    if stack == "security_groups":
        network = False
        security_groups = True
        webserver = False
        bigip = False

    if stack == "infra":
        network = True
        security_groups = True
        webserver = True
        bigip = False

    if stack == "full":
        network = True
        security_groups = True
        webserver = True
        bigip = True

    if stack == "existing":
        network = False
        security_groups = False
        webserver = False
        bigip = True


    # Begin Template
    t = Template()
    t.add_version("2010-09-09")
    version = "1.0.0"
    description = "Template Version " + str(version) + ": "
    if stack == "network":
        description += "AWS CloudFormation Template for creating network components for a " + str(num_azs) + " Availability Zone VPC"
    elif stack == "security_groups":
        description += "AWS CloudFormation Template for creating security groups for a " + str(num_nics) + "NIC BIG-IP"
    elif stack == "infra":
        description += "AWS CloudFormation Template for creating a " + str(num_azs) + " Availability Zone VPC, subnets, security groups and a webserver (Bitnami LAMP stack with username bitnami **WARNING** This template creates Amazon EC2 Instances. You will be billed for the AWS resources used if you create a stack from this template."
    elif stack == "full":
        if ha_type == "standalone":
            description += "AWS CloudFormation Template for creating a full stack with a " + str(num_nics) + "NIC BIG-IP, a " + str(num_azs) + " Availability Zone VPC, subnets, security groups and a webserver (Bitnami LAMP stack with username bitnami **WARNING** This template creates Amazon EC2 Instances. You will be billed for the AWS resources used if you create a stack from this template."
        if ha_type == "same-az":
            description += "AWS CloudFormation Template for creating a full stack with a Same-AZ cluster of " + str(num_nics) + "NIC BIG-IPs, a " + str(num_azs) + " Availability Zone VPC, subnets, security groups and a webserver (Bitnami LAMP stack with username bitnami **WARNING** This template creates Amazon EC2 Instances. You will be billed for the AWS resources used if you create a stack from this template."
        if ha_type == "across-az":
            description += "AWS CloudFormation Template for creating a full stack with a Across-AZs cluster of " + str(num_nics) + "NIC BIG-IPs, a " + str(num_azs) + " Availability Zone VPC, subnets, security groups and a webserver (Bitnami LAMP stack with username bitnami **WARNING** This template creates Amazon EC2 Instances. You will be billed for the AWS resources used if you create a stack from this template."
    elif stack == "existing":
        if ha_type == "standalone":
            description += "AWS CloudFormation Template for creating a " + str(num_nics) + "NIC BIG-IP in an existing VPC **WARNING** This template creates Amazon EC2 Instances. You will be billed for the AWS resources used if you create a stack from this template."
        if ha_type == "same-az":
            description += "AWS CloudFormation Template for creating a Same-AZ cluster of " + str(num_nics) + "NIC BIG-IPs in an existing VPC **WARNING** This template creates Amazon EC2 Instances. You will be billed for the AWS resources used if you create a stack from this template."
        if ha_type == "across-az":
            description += "AWS CloudFormation Template for creating a Across-AZs cluster of " + str(num_nics) + "NIC BIG-IPs in an existing VPC **WARNING** This template creates Amazon EC2 Instances. You will be billed for the AWS resources used if you create a stack from this template."

    t.add_description(description)
    t.add_metadata({
        "Version": str(version),
        "AWS::CloudFormation::Interface": {
          "ParameterGroups": [
            {
              "Label": {
                  "default": "NETWORKING CONFIGURATION"
              },
              "Parameters": [
                "Vpc",
                "managementSubnetAz1",
                "managementSubnetAz2",
                "subnet1Az2",
                "bigipManagementSecurityGroup",
                "subnet1Az1",
                "bigipExternalSecurityGroup",
                "availabilityZone1",
                "availabilityZone2"
              ]
            },
            {
              "Label": {
                  "default": "INSTANCE CONFIGURATION"
                },
              "Parameters": [
                "adminUsername",           
                "adminPassword",
                "imageName",
                "instanceType",
                "applicationInstanceType",
                "licenseKey1",
                "licenseKey2",
                "managementGuiPort",
                "sshKey",
                "restrictedSrcAddress",
                "iamAccessKey",
                "iamSecretKey"
              ]
            },
            {
              "Label": {
                "default": "TAGS"
              },
              "Parameters": [
                    "application",
                    "environment",
                    "group",
                    "owner",
                    "costcenter"
              ]
            },
          ],
          "ParameterLabels": {
           "Vpc": {
                "default": "VPC"
            },
            "managementSubnetAz1": {
                "default": "Management Subnet AZ1"
            },
            "managementSubnetAz2": {
                "default": "Management Subnet AZ2"
            },
            "subnet1Az1": {
                "default": "Subnet AZ1"
            },
            "subnet1Az2": {
                "default": "Subnet AZ2"
            },
            "availabilityZone1": {
                "default": "Availability Zone 1"
            },
            "availabilityZone2": {
                "default": "Availability Zone 2"
            },
            "bigipManagementSecurityGroup": {
                "default": "Management Security Group"
            },
            "bigipExternalSecurityGroup": {
                "default": "External Security Group"
            },
            "adminUsername": {
                "default": "Admin Username"
            },
            "adminPassword": {
                "default": "Admin Password"
            },
            "imageName": {
                "default": "Image Name"
            },
            "instanceType": {
                "default": "AWS Instance Size"
            },
            "applicationInstanceType": {
                "default": "Application Instance Type"
            },
            "licenseKey1": {
                "default": "License Key1"
            },
            "restrictedSrcAddress": {
                "default": "Source Address(es) for SSH Access"
            },
            "iamAccessKey": {
                "default": "IAM Access Key"
            },
            "iamSecretKey": {
                "default": "IAM Secret Key"
            },            
            "managementGuiPort": {
                "default": "Management Port"
            },
            "sshKey": {
                "default": "SSH Key"
            },
            "application": {
                "default": "Application"
            },
            "environment": {
                "default": "Environment"
            },
            "group": {
                "default": "Group"
            },
            "owner": {
                "default": "Owner"
            },
            "costcenter": {
                "default": "Cost Center"
            }
          }
        }
    }
    )

    ### BEGIN PARAMETERS

    application = t.add_parameter (Parameter(
        "application",
            Description="Name of the Application Tag",
            Default="f5app",
            Type="String",
    ))
    environment = t.add_parameter (Parameter(
        "environment",
            Description="Name of the Environment Tag",
            Default="f5env",
            Type="String",
    ))
    group = t.add_parameter (Parameter(
        "group",
            Description="Name of the Group Tag",
            Default="f5group",
            Type="String",
    ))
    owner = t.add_parameter (Parameter(
        "owner",
            Description="Name of the Owner Tag",
            Default="f5owner",
            Type="String",
    ))
    costcenter = t.add_parameter (Parameter(
        "costcenter",
            Description="Name of the Cost Center Tag",
            Default="f5costcenter",
            Type="String",
    ))    
    if stack != "network": 
        restrictedSrcAddress = t.add_parameter(Parameter(
            "restrictedSrcAddress",

            ConstraintDescription="Must be a valid IP CIDR range of the form x.x.x.x/x.",
            Description=" The IP address range that can be used to SSH to the EC2 instances",
            Default="0.0.0.0/0",
            MinLength="9",
            AllowedPattern="(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})/(\\d{1,2})",
            MaxLength="18",
            Type="String",
        ))

    if stack != "network" and stack != "security_groups":
        sshKey = t.add_parameter(Parameter(
            "sshKey",
            Type="AWS::EC2::KeyPair::KeyName",
            Description="Key pair for accessing the instance",
        ))


    if network == True:

        for INDEX in range(num_azs):
            AvailabilityZone = "availabilityZone" + str(INDEX + 1)
            PARAMETERS[AvailabilityZone] = t.add_parameter(Parameter(
                AvailabilityZone,
            Type="AWS::EC2::AvailabilityZone::Name",
            Description="Name of an Availability Zone in this Region",
        ))

    if webserver == True:
        applicationInstanceType = t.add_parameter(Parameter(
            "applicationInstanceType",
            Default="t1.micro",
            ConstraintDescription="Must be a valid EC2 instance type",
            Type="String",
            Description="Webserver EC2 instance type",
            AllowedValues=["t1.micro", "m3.medium", "m3.xlarge", "m2.xlarge", "m3.2xlarge", "c3.large", "c3.xlarge"],
        ))


    if bigip == True or security_groups == True:
        if num_nics == 1:
            managementGuiPort = t.add_parameter(Parameter(
                "managementGuiPort",
                Default="8443",
                ConstraintDescription="Must be a valid, unused port on the BIG-IP.",
                Type="Number",
                Description="Port for the BIG-IP management Configuration utility",
            ))

    if bigip == True:
        if 'waf' in components:
            # Default to 2xlarge
            instanceType = t.add_parameter(Parameter(
                "instanceType",
                Default="m3.2xlarge",
                ConstraintDescription="Must be a valid EC2 instance type for BIG-IP",
                Type="String",
                Description="AWS instance type",
                AllowedValues=[
                                "m3.2xlarge",
                                "m4.2xlarge",
                                "m4.4xlarge",
                                "m4.10xlarge",
                                "c3.4xlarge",
                                "c3.8xlarge",
                                "c4.4xlarge",       
                                "c4.8xlarge",
                                "cc2.8xlarge",
                              ],
            ))
        else:
            instanceType = t.add_parameter(Parameter(
                "instanceType",
                Default="m3.2xlarge",
                ConstraintDescription="Must be a valid EC2 instance type for BIG-IP",
                Type="String",
                Description="Size of the F5 BIG-IP Virtual Instance",
                AllowedValues=[
                                "t2.medium",
                                "t2.large",
                                "m3.xlarge",
                                "m3.2xlarge",
                                "m4.large",
                                "m4.xlarge",
                                "m4.2xlarge",
                                "m4.4xlarge",
                                "m4.10xlarge",
                                "c3.2xlarge",
                                "c3.4xlarge",
                                "c3.8xlarge",
                                "c4.xlarge",
                                "c4.2xlarge",
                                "c4.4xlarge",       
                              ],
            ))

        if license_type == "hourly" and 'waf' not in components:
            imageName = t.add_parameter(Parameter(
                "imageName",
                Default="Best1000Mbps",
                ConstraintDescription="Must be a valid F5 BIG-IP VE image type",
                Type="String",
                Description="F5 BIG-IP VE image",
                AllowedValues=[
                                "Good25Mbps",
                                "Good200Mbps",
                                "Good1000Mbps",    
                                "Better25Mbps",
                                "Better200Mbps",
                                "Better1000Mbps",                          
                                "Best25Mbps",
                                "Best200Mbps",
                                "Best1000Mbps",
                              ],
            ))
        if license_type == "hourly" and 'waf' in components:
            imageName = t.add_parameter(Parameter(
                "imageName",
                Default="Best1000Mbps",
                ConstraintDescription="Must be a valid F5 BIG-IP VE image type",
                Type="String",
                Description="F5 BIG-IP Performance Type",
                AllowedValues=[                     
                                "Best25Mbps",
                                "Best200Mbps",
                                "Best1000Mbps",
                              ],
            ))
        if license_type != "hourly":
            imageName = t.add_parameter(Parameter(
                "imageName",
                Default="Best",
                ConstraintDescription="Must be a valid F5 BIG-IP VE image type",
                Type="String",
                Description="F5 BIG-IP Performance Type",
                AllowedValues=["Good", "Better", "Best"],
            ))
        adminUsername = t.add_parameter(Parameter(
            "adminUsername",
            Type="String",
            Description="BIG-IP VE Admin Username",
            Default="admin",
            MinLength="1",
            MaxLength="255",
            ConstraintDescription="Verify your BIG-IP VE Admin Username",
        ))

        adminPassword = t.add_parameter(Parameter(
            "adminPassword",
            Type="String",
            Description="BIG-IP VE Admin Password",
            MinLength="1",
            NoEcho=True,
            MaxLength="255",
            ConstraintDescription="Verify your BIG-IP VE Admin Password",
        ))
        if aws_creds == True:
            iamAccessKey = t.add_parameter(Parameter(
                "iamAccessKey",
                Description="IAM Access key ID",
                Type="String",
                MinLength="16",
                MaxLength="32",
                AllowedPattern="[\\w]*",
                NoEcho=True,
                ConstraintDescription="Can contain only ASCII characters.",
            ))
            iamSecretKey = t.add_parameter(Parameter(
                "iamSecretKey",
                Description="IAM Secret access key",
                Type="String",
                MinLength="1",
                MaxLength="255",
                AllowedPattern="[\\x20-\\x7E]*",
                NoEcho=True,
                ConstraintDescription="Can contain only ASCII characters.",
            ))
        if license_type == "byol":
            for BIGIP_INDEX in range(num_bigips): 
                licenseKey = "licenseKey" + str(BIGIP_INDEX + 1)
                PARAMETERS[licenseKey] = t.add_parameter(Parameter(
                    licenseKey,
                    Type="String",
                    Description="F5 BYOL license key",
                    MinLength="1",
                    AllowedPattern="([\\x41-\\x5A][\\x41-\\x5A|\\x30-\\x39]{4})\\-([\\x41-\\x5A|\\x30-\\x39]{5})\\-([\\x41-\\x5A|\\x30-\\x39]{5})\\-([\\x41-\\x5A|\\x30-\\x39]{5})\\-([\\x41-\\x5A|\\x30-\\x39]{7})",
                    MaxLength="255",
                    ConstraintDescription="Verify your F5 BYOL regkey.",
                ))
        if license_type == "bigiq":
            bigiqAddress = t.add_parameter(Parameter(
                "bigiqAddress",
                MinLength="1",
                ConstraintDescription="Verify your BIG-IQ Hostname or IP",
                Type="String",
                Description="BIG-IQ Hostname or IP",
                MaxLength="255",
            ))
            bigiqUsername = t.add_parameter(Parameter(
                "bigiqUsername",
                MinLength="1",
                ConstraintDescription="Verify your BIG-IQ Username.",
                Type="String",
                Description="BIG-IQ Username",
                MaxLength="255",
            ))
            bigiqPassword = t.add_parameter(Parameter(
                "bigiqPassword",
                Type="String",
                Description="BIG-IQ Password",
                MinLength="1",
                NoEcho=True,
                MaxLength="255",
                ConstraintDescription="Verify your BIG-IQ Password",
            ))
            bigiqLicensePoolUUID = t.add_parameter(Parameter(
                "bigiqLicensePoolUUID",
                MinLength="1",
                ConstraintDescription="Verify your BIG-IQ License Pool UUID",
                Type="String",
                Description="BIG-IQ License Pool UUID",
                MaxLength="255",
            ))
    if stack == "existing" or stack == "security_groups":
            Vpc = t.add_parameter(Parameter(
                "Vpc",
                ConstraintDescription="This must be an existing VPC within the working region.",
                Type="AWS::EC2::VPC::Id",
            ))

    if stack == "existing":
        for INDEX in range(num_azs):
            ExternalSubnet = "subnet1" + "Az" + str(INDEX + 1)
            PARAMETERS[ExternalSubnet] = t.add_parameter(Parameter(
                ExternalSubnet,
                ConstraintDescription="The subnet ID must be within an existing VPC",
                Type="AWS::EC2::Subnet::Id",
                Description="Public or External subnet",
            ))
        bigipExternalSecurityGroup = t.add_parameter(Parameter(
            "bigipExternalSecurityGroup",
            ConstraintDescription="The security group ID must be within an existing VPC",
            Type="AWS::EC2::SecurityGroup::Id",
            Description="Public or External Security Group",
        ))
        if num_nics > 1:
            for INDEX in range(num_azs):
                managementSubnet = "managementSubnet" + "Az" + str(INDEX + 1)
                PARAMETERS[managementSubnet] = t.add_parameter(Parameter(
                    managementSubnet,
                    ConstraintDescription="The subnet ID must be within an existing VPC",
                    Type="AWS::EC2::Subnet::Id",
                    Description="Management Subnet ID",
                ))
            bigipManagementSecurityGroup = t.add_parameter(Parameter(
                "bigipManagementSecurityGroup",
                ConstraintDescription="The security group ID must be within an existing VPC",
                Type="AWS::EC2::SecurityGroup::Id",
                Description="BIG-IP Management Security Group",
            ))
        if num_nics > 2:
            for INDEX in range(num_azs):
                InternalSubnet = "subnet2" + "Az" + str(INDEX + 1)
                PARAMETERS[InternalSubnet] = t.add_parameter(Parameter(
                    InternalSubnet,
                    ConstraintDescription="The subnet ID must be within an existing VPC",
                    Type="AWS::EC2::Subnet::Id",
                    Description="Private or Internal subnet ID",
                ))
            bigipInternalSecurityGroup = t.add_parameter(Parameter(
                "bigipInternalSecurityGroup",
                ConstraintDescription="The security group ID must be within an existing VPC",
                Type="AWS::EC2::SecurityGroup::Id",
                Description="Private or Internal Security Group ID",
            ))

    # BEGIN REGION MAPPINGS FOR AMI IDS
    if bigip == True: 

        if license_type == "hourly":
            with open("cached-hourly-region-map.json") as json_file:
                RegionMap = json.load(json_file)

        if license_type != "hourly":
            with open("cached-byol-region-map.json") as json_file:
                RegionMap = json.load(json_file)

        t.add_mapping("BigipRegionMap", RegionMap )

    # WEB SERVER MAPPING
    if webserver == True:

        with open("cached-webserver-region-map.json") as json_file:
            RegionMap = json.load(json_file)

        t.add_mapping("WebserverRegionMap", RegionMap )


    ### BEGIN RESOURCES
    if network == True:
        Vpc = t.add_resource(VPC(
            "Vpc",
            EnableDnsSupport="true",
            CidrBlock="10.0.0.0/16",
            EnableDnsHostnames="true",
            Tags=Tags(
                Name=Join("", ["Vpc: ", Ref("AWS::StackName")] ),
                Application=Ref("application"),
                Environment=Ref("environment"),
                Group=Ref("group"),
                Owner=Ref("owner"),
                Costcenter=Ref("costcenter"),
            ),
        ))

        defaultGateway = t.add_resource(InternetGateway(
            "InternetGateway",
            Tags=Tags(
                        Name=Join("", ["InternetGateway: ", Ref("AWS::StackName")] ),
                        Application=Ref(application),
                        Environment=Ref(environment),
                        Group=Ref(group),
                        Owner=Ref(owner),
                        Costcenter=Ref(costcenter),
            ),
        ))

        AttachGateway = t.add_resource(VPCGatewayAttachment(
            "AttachGateway",

            VpcId=Ref(Vpc),
            InternetGatewayId=Ref(defaultGateway),
        ))

        octet = 1
        for INDEX in range(num_azs):
            ExternalSubnet = "subnet1" + "Az" + str(INDEX + 1)

            RESOURCES[ExternalSubnet] = t.add_resource(Subnet(
                ExternalSubnet,

                Tags=Tags(
                    Name=Join("", ["Az" , str(INDEX + 1) ,  " External Subnet:" , Ref("AWS::StackName")] ),
                    Application=Ref("application"),
                    Environment=Ref("environment"),
                    Group=Ref("group"),
                    Owner=Ref("owner"),
                    Costcenter=Ref("costcenter"),
                ),
                VpcId=Ref(Vpc),
                CidrBlock="10.0." + str(octet) + ".0/24",
                AvailabilityZone=Ref("availabilityZone" + str(INDEX + 1) ),
            ))
            octet += 10

        ExternalRouteTable = t.add_resource(RouteTable(
            "ExternalRouteTable",

            VpcId=Ref(Vpc),
            Tags=Tags(
                Name=Join("", ["External Route Table", Ref("AWS::StackName")] ),
                Application=Ref("application"),
                Environment=Ref("environment"),
                Group=Ref("group"),
                Owner=Ref("owner"),
                Costcenter=Ref("costcenter"),
                Network="External",
            ),
        ))

        ExternalDefaultRoute = t.add_resource(Route(
            "ExternalDefaultRoute",

            DependsOn="AttachGateway",
            GatewayId=Ref(defaultGateway),
            DestinationCidrBlock="0.0.0.0/0",
            RouteTableId=Ref(ExternalRouteTable),
        ))

        for INDEX in range(num_azs):
            ExternalSubnetRouteTableAssociation = "Az" + str(INDEX + 1) + "ExternalSubnetRouteTableAssociation"

            RESOURCES[ExternalSubnetRouteTableAssociation] = t.add_resource(SubnetRouteTableAssociation(
                ExternalSubnetRouteTableAssociation,

                SubnetId=Ref("subnet1" + "Az" + str(INDEX + 1)),
                RouteTableId=Ref(ExternalRouteTable),
            ))
           

        if num_nics > 1:
            octet = 0

            for INDEX in range(num_azs):
                managementSubnet = "managementSubnet" + "Az" + str(INDEX + 1)

                RESOURCES[managementSubnet] = t.add_resource(Subnet(
                    managementSubnet,

                    Tags=Tags(
                        Name=Join("", ["Az" , str(INDEX + 1) ,  " Management Subnet:" , Ref("AWS::StackName")] ),
                        Application=Ref("application"),
                        Environment=Ref("environment"),
                        Group=Ref("group"),
                        Owner=Ref("owner"),
                        Costcenter=Ref("costcenter"),
                    ),
                    VpcId=Ref(Vpc),
                    CidrBlock="10.0." + str(octet) + ".0/24",
                    AvailabilityZone=Ref("availabilityZone" + str(INDEX + 1) ),
                ))
                octet += 10

            ManagementRouteTable = t.add_resource(RouteTable(
                "ManagementRouteTable",

                VpcId=Ref(Vpc),
                Tags=Tags(
                    Name=Join("", ["Management Route Table", Ref("AWS::StackName")] ),
                    Application=Ref("application"),
                    Environment=Ref("environment"),
                    Group=Ref("group"),
                    Owner=Ref("owner"),
                    Costcenter=Ref("costcenter"),
                    Network="Mgmt",
                ),
            ))

            # Depends On
            #https://forums.aws.amazon.com/thread.jspa?threadID=100750
            ManagementDefaultRoute = t.add_resource(Route(
                "ManagementDefaultRoute",
                DependsOn="AttachGateway",


                GatewayId=Ref(defaultGateway),
                DestinationCidrBlock="0.0.0.0/0",
                RouteTableId=Ref(ManagementRouteTable),
            ))
    
            for INDEX in range(num_azs):
                ManagementSubnetRouteTableAssociation = "Az" + str(INDEX + 1) + "ManagementSubnetRouteTableAssociation"

                RESOURCES[ManagementSubnetRouteTableAssociation] = t.add_resource(SubnetRouteTableAssociation(
                    ManagementSubnetRouteTableAssociation,

                    SubnetId=Ref("managementSubnet" + "Az" + str(INDEX + 1)),
                    RouteTableId=Ref(ManagementRouteTable),

                ))


        if num_nics > 2:
            octet = 2
            for INDEX in range(num_azs):
                InternalSubnet = "subnet2" + "Az" + str(INDEX + 1)

                RESOURCES[InternalSubnet] = t.add_resource(Subnet(
                    InternalSubnet,

                    Tags=Tags(
                        Name=Join("", ["Az" , str(INDEX + 1) ,  " Internal Subnet:" , Ref("AWS::StackName")] ),
                        Application=Ref("application"),
                        Environment=Ref("environment"),
                        Group=Ref("group"),
                        Owner=Ref("owner"),
                        Costcenter=Ref("costcenter"),
                    ),
                    VpcId=Ref(Vpc),
                    CidrBlock="10.0." + str(octet) + ".0/24",
                    AvailabilityZone=Ref("availabilityZone" + str(INDEX + 1) ),
                ))
                octet += 10


            InternalRouteTable = t.add_resource(RouteTable(
                "InternalRouteTable",

                VpcId=Ref(Vpc),
                Tags=Tags(
                    Name=Join("", ["Internal Route Table:", Ref("AWS::StackName")] ),
                    Application=Ref("application"),
                    Environment=Ref("environment"),
                    Group=Ref("group"),
                    Owner=Ref("owner"),
                    Costcenter=Ref("costcenter"),
                    Network="Internal",
                ),
            ))

            InternalDefaultRoute = t.add_resource(Route(
                "InternalDefaultRoute",
                DependsOn="AttachGateway",


                GatewayId=Ref(defaultGateway),
                DestinationCidrBlock="0.0.0.0/0",
                RouteTableId=Ref(InternalRouteTable),
            ))

            for INDEX in range(num_azs):
                InternalSubnetRouteTableAssociation = "Az" + str(INDEX + 1) + "InternalSubnetRouteTableAssociation"

                RESOURCES[InternalSubnetRouteTableAssociation] = t.add_resource(SubnetRouteTableAssociation(
                    InternalSubnetRouteTableAssociation,

                    SubnetId=Ref("subnet2" + "Az" + str(INDEX + 1)),
                    RouteTableId=Ref(InternalRouteTable),

                ))

        octet = 3
        for INDEX in range(num_azs):
            ApplicationSubnet = "Az" + str(INDEX + 1) + "ApplicationSubnet"
            RESOURCES[ApplicationSubnet] = t.add_resource(Subnet(
                ApplicationSubnet,
                Tags=Tags(
                    Name=Join("", ["Az" , str(INDEX + 1) ,  " Application Subnet:" , Ref("AWS::StackName")] ),             
                    Application=Ref("application"),
                    Environment=Ref("environment"),
                    Group=Ref("group"),
                    Owner=Ref("owner"),
                    Costcenter=Ref("costcenter"),
                ),
                VpcId=Ref(Vpc),
                CidrBlock="10.0." + str(octet) + ".0/24",
                AvailabilityZone=Ref("availabilityZone" + str(INDEX + 1) ),
            ))
            octet += 10

        ApplicationRouteTable = t.add_resource(RouteTable(
            "ApplicationRouteTable",
            VpcId=Ref(Vpc),
            Tags=Tags(
                Name=Join("", ["Application Route Table:", Ref("AWS::StackName")] ),
                Application=Ref("application"),
                Environment=Ref("environment"),
                Group=Ref("group"),
                Owner=Ref("owner"),
                Costcenter=Ref("costcenter"),
                Network="Application",
            ),
        ))

        ApplicationDefaultRoute = t.add_resource(Route(
            "ApplicationDefaultRoute",
            DependsOn="AttachGateway",
            GatewayId=Ref(defaultGateway),
            DestinationCidrBlock="0.0.0.0/0",
            RouteTableId=Ref(ApplicationRouteTable),
        ))


        for INDEX in range(num_azs):
            ApplicationSubnetRouteTableAssociation = "Az" + str(INDEX + 1) + "ApplicationSubnetRouteTableAssociation"
            RESOURCES[ApplicationSubnetRouteTableAssociation] = t.add_resource(SubnetRouteTableAssociation(
                ApplicationSubnetRouteTableAssociation,
                SubnetId=Ref("Az" + str(INDEX + 1) + "ApplicationSubnet"),
                RouteTableId=Ref(ApplicationRouteTable),
            ))

    # See SOL13946 for more details
    # Clustering uses UDP 1026 UDP (failover) and TCP 4353 (SYNC) 
    # WAF uses 6123-6128 for SYNC
    # As just examples, not going to break down example Security Groups for Cluster & WAF. 
    # However, could further tighten if Standalone or no WAF.  

    if security_groups == True:

        # 1 Nic has consolidated rules
        if num_nics == 1:

            bigipExternalSecurityGroup = t.add_resource(SecurityGroup(
                "bigipExternalSecurityGroup",

                SecurityGroupIngress=[
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="22",
                                ToPort="22",
                                CidrIp=Ref(restrictedSrcAddress),

                    ),
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort=Ref(managementGuiPort),
                                ToPort=Ref(managementGuiPort),
                                CidrIp=Ref(restrictedSrcAddress),



                    ),
                    SecurityGroupRule(
                                IpProtocol="icmp",
                                FromPort="-1",
                                ToPort="-1",
                                CidrIp=Ref(restrictedSrcAddress),

                    ),         
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="80",
                                ToPort="80",
                                CidrIp="0.0.0.0/0",
                    ),
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="443",
                                ToPort="443",
                                CidrIp="0.0.0.0/0",
                    ),
                    # Required Device Service Clustering (DSC) & GTM DNS
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="4353",
                                ToPort="4353",
                                CidrIp="0.0.0.0/0",
                    ),
                    # Required for DSC Initial Sync
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="22",
                                ToPort="22",
                                CidrIp="10.0.0.0/16",
                    ), 
                    # Required for DSC Network Heartbeat
                    SecurityGroupRule(
                                IpProtocol="udp",
                                FromPort="1026",
                                ToPort="1026",
                                CidrIp="10.0.0.0/16",
                    ), 
                    # ASM SYNC
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="6123",
                                ToPort="6128",
                                CidrIp="10.0.0.0/16",
                    ),
                ],
                VpcId=Ref(Vpc),
                GroupDescription="Public or External interface rules",
                Tags=Tags(
                    Name=Join("", ["Bigip Security Group: ", Ref("AWS::StackName")] ),
                    Application=Ref("application"),
                    Environment=Ref("environment"),
                    Group=Ref("group"),
                    Owner=Ref("owner"),
                    Costcenter=Ref("costcenter"),
                ),
            ))


        if num_nics > 1:

            bigipExternalSecurityGroup = t.add_resource(SecurityGroup(
                "bigipExternalSecurityGroup",

                SecurityGroupIngress=[
                    # Example port for Virtual Server
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="80",
                                ToPort="80",
                                CidrIp="0.0.0.0/0",
                    ),
                    # Example port for Virtual Server
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="443",
                                ToPort="443",
                                CidrIp="0.0.0.0/0",
                    ),
                    # Required Device Service Clustering (DSC) & GTM DNS
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="4353",
                                ToPort="4353",
                                CidrIp="0.0.0.0/0",
                    ),
                    # Required for DSC Network Heartbeat
                    SecurityGroupRule(
                                IpProtocol="udp",
                                FromPort="1026",
                                ToPort="1026",
                                CidrIp="10.0.0.0/16",
                    ), 
                    # ASM SYNC
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="6123",
                                ToPort="6128",
                                CidrIp="10.0.0.0/16",
                    ),

                ],
                VpcId=Ref(Vpc),
                GroupDescription="Public or External interface rules",
                Tags=Tags(
                    Name=Join("", ["Bigip External Security Group:", Ref("AWS::StackName")] ),
                    Application=Ref("application"),
                    Environment=Ref("environment"),
                    Group=Ref("group"),
                    Owner=Ref("owner"),
                    Costcenter=Ref("costcenter"),
                ),
            ))
            

            bigipManagementSecurityGroup = t.add_resource(SecurityGroup(
                "bigipManagementSecurityGroup",

                SecurityGroupIngress=[
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="22",
                                ToPort="22",
                                CidrIp=Ref(restrictedSrcAddress),

                    ),
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="443",
                                ToPort="443",
                                CidrIp=Ref(restrictedSrcAddress),

                    ),
                    SecurityGroupRule(
                                IpProtocol="icmp",
                                FromPort="-1",
                                ToPort="-1",
                                CidrIp=Ref(restrictedSrcAddress),

                    ),
                    # Required for DSC Initial Sync
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="22",
                                ToPort="22",
                                CidrIp="10.0.0.0/16",
                    ),
                    # Required for DSC Initial Sync
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="443",
                                ToPort="443",
                                CidrIp="10.0.0.0/16",
                    ),  
                ],
                VpcId=Ref(Vpc),
                GroupDescription="BIG-IP Management UI rules",
                Tags=Tags(
                    Name=Join("", ["Bigip Management Security Group:", Ref("AWS::StackName")] ),
                    Application=Ref("application"),
                    Environment=Ref("environment"),
                    Group=Ref("group"),
                    Owner=Ref("owner"),
                    Costcenter=Ref("costcenter"),
                ),
            ))

        # If a 3 nic with additional Internal interface.
        if num_nics > 2:

            bigipInternalSecurityGroup = t.add_resource(SecurityGroup(
                "bigipInternalSecurityGroup",

                SecurityGroupIngress=[
                    SecurityGroupRule(
                                IpProtocol="-1",
                                FromPort="-1",
                                ToPort="-1",
                                CidrIp="10.0.0.0/16",
                    ),
                ],
                VpcId=Ref(Vpc),
                GroupDescription="Allow All from Intra-VPC only",
                Tags=Tags(
                    Name=Join("", ["Bigip Internal Security Group:", Ref("AWS::StackName")] ),
                    Application=Ref("application"),
                    Environment=Ref("environment"),
                    Group=Ref("group"),
                    Owner=Ref("owner"),
                    Costcenter=Ref("costcenter"),
                ),
            ))

        if webserver == True:

            WebserverSecurityGroup = t.add_resource(SecurityGroup(
                "WebserverSecurityGroup",
                SecurityGroupIngress=[
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="22",
                                ToPort="22",
                                CidrIp="0.0.0.0/0",
                    ),
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="80",
                                ToPort="80",
                                CidrIp="0.0.0.0/0",
                    ),
                    SecurityGroupRule(
                                IpProtocol="tcp",
                                FromPort="443",
                                ToPort="443",
                                CidrIp="0.0.0.0/0",
                    ),
                    SecurityGroupRule(
                                IpProtocol="icmp",
                                FromPort="-1",
                                ToPort="-1",
                                CidrIp="0.0.0.0/0",
                    ),
                ],
                VpcId=Ref(Vpc),
                GroupDescription="Enable Access to Webserver",
                Tags=Tags(
                    Name=Join("", ["Webserver Security Group:", Ref("AWS::StackName")] ),
                    Application=Ref("application"),
                    Environment=Ref("environment"),
                    Group=Ref("group"),
                    Owner=Ref("owner"),
                    Costcenter=Ref("costcenter"),
                ),
            ))

    if webserver == True:

        Webserver = t.add_resource(Instance(
            "Webserver",
            UserData=Base64(Join("\n", [
                                         "#cloud-config",
                                         "runcmd:",
                                         " - sudo docker run --name demo -p 80:80 -d f5devcentral/f5-demo-app:latest"
                ])),
            Tags=Tags(
                Name=Join("", ["Webserver:", Ref("AWS::StackName")] ),
                Application=Ref("application"),
                Environment=Ref("environment"),
                Group=Ref("group"),
                Owner=Ref("owner"),
                Costcenter=Ref("costcenter"),
            ),
            ImageId=FindInMap("WebserverRegionMap", Ref("AWS::Region"), "AMI"),
            KeyName=Ref(sshKey),
            InstanceType=Ref(applicationInstanceType),
            NetworkInterfaces=[
            NetworkInterfaceProperty(
                SubnetId=Ref("Az1ApplicationSubnet"),
                DeviceIndex="0",
                GroupSet=[Ref(WebserverSecurityGroup)],
                Description=Join("", [Ref("AWS::StackName"), " Webserver Network Interface"]),
                AssociatePublicIpAddress="true",
            ),
            ],
        ))


    if bigip == True:

        for BIGIP_INDEX in range(num_bigips): 

            licenseKey = "licenseKey" + str(BIGIP_INDEX + 1)
            BigipInstance = "Bigip" + str(BIGIP_INDEX + 1) + "Instance"

            if num_azs > 1:
                ExternalSubnet = "subnet1" + "Az" + str(BIGIP_INDEX + 1)
                managementSubnet = "managementSubnet" + "Az" + str(BIGIP_INDEX + 1)
                InternalSubnet = "subnet2" + "Az" + str(BIGIP_INDEX + 1)              

            else:
                ExternalSubnet = "subnet1Az1"
                managementSubnet = "managementSubnetAz1"
                InternalSubnet = "subnet2Az1"
            ExternalSelfEipAddress = "Bigip" + str(BIGIP_INDEX + 1) + str(ExternalSubnet) + "SelfEipAddress"            
            ExternalInterface = "Bigip" + str(BIGIP_INDEX + 1) + str(ExternalSubnet) + "Interface"
            ExternalSelfEipAssociation = "Bigip" + str(BIGIP_INDEX + 1) + str(ExternalSubnet) + "SelfEipAssociation"


            RESOURCES[ExternalInterface] = t.add_resource(NetworkInterface(
                ExternalInterface,
                SubnetId=Ref(ExternalSubnet),
                GroupSet=[Ref(bigipExternalSecurityGroup)],



                Description="Public External Interface for the BIG-IP",
                SecondaryPrivateIpAddressCount="1",
            ))

            if stack == "full":
                # External Interface is true on 1nic,2nic,3nic,etc.
                RESOURCES[ExternalSelfEipAddress] = t.add_resource(EIP(    
                    ExternalSelfEipAddress,
                    DependsOn="AttachGateway",


                    Domain="vpc",
                ))

                RESOURCES[ExternalSelfEipAssociation] = t.add_resource(EIPAssociation(
                    ExternalSelfEipAssociation,
                    DependsOn="AttachGateway",


                    NetworkInterfaceId=Ref(ExternalInterface),
                    AllocationId=GetAtt(ExternalSelfEipAddress, "AllocationId"),
                    PrivateIpAddress=GetAtt(ExternalInterface, "PrimaryPrivateIpAddress"),
                ))
            else:
                RESOURCES[ExternalSelfEipAddress] = t.add_resource(EIP(    
                    ExternalSelfEipAddress,

                    Domain="vpc",
                ))

                RESOURCES[ExternalSelfEipAssociation] = t.add_resource(EIPAssociation(
                    ExternalSelfEipAssociation,

                    NetworkInterfaceId=Ref(ExternalInterface),
                    AllocationId=GetAtt(ExternalSelfEipAddress, "AllocationId"),
                    PrivateIpAddress=GetAtt(ExternalInterface, "PrimaryPrivateIpAddress"),
                ))
         
            if num_nics > 1:

                VipEipAddress = "Bigip" + str(BIGIP_INDEX + 1) + "VipEipAddress"
                VipEipAssociation = "Bigip" + str(BIGIP_INDEX + 1) + "VipEipAssociation"
                ManagementInterface = "Bigip" + str(BIGIP_INDEX + 1) + "ManagementInterface"
                ManagementEipAddress = "Bigip" + str(BIGIP_INDEX + 1) + "ManagementEipAddress"
                ManagementEipAssociation = "Bigip" + str(BIGIP_INDEX + 1) + "ManagementEipAssociation"

                if ha_type == "standalone" or (BIGIP_INDEX + 1) == CLUSTER_SEED:

                    if stack == "full":
                        RESOURCES[VipEipAddress] = t.add_resource(EIP(
                            VipEipAddress,
                            DependsOn="AttachGateway",


                            Domain="vpc",
                        ))
                        RESOURCES[VipEipAssociation] = t.add_resource(EIPAssociation(
                            VipEipAssociation,
                            DependsOn="AttachGateway",


                            NetworkInterfaceId=Ref(ExternalInterface),
                            AllocationId=GetAtt(VipEipAddress, "AllocationId"),
                            PrivateIpAddress=Select("0", GetAtt(ExternalInterface, "SecondaryPrivateIpAddresses")),
                        ))
                    else:
                        RESOURCES[VipEipAddress] = t.add_resource(EIP(
                            VipEipAddress,

                            Domain="vpc",
                        ))
                        RESOURCES[VipEipAssociation] = t.add_resource(EIPAssociation(
                            VipEipAssociation,

                            NetworkInterfaceId=Ref(ExternalInterface),
                            AllocationId=GetAtt(VipEipAddress, "AllocationId"),
                            PrivateIpAddress=Select("0", GetAtt(ExternalInterface, "SecondaryPrivateIpAddresses")),
                        ))

                RESOURCES[ManagementInterface] = t.add_resource(NetworkInterface(
                    ManagementInterface,
                    SubnetId=Ref(managementSubnet),
                    GroupSet=[Ref(bigipManagementSecurityGroup)],



                    Description="Management Interface for the BIG-IP",
                ))

                if stack == "full":
                    RESOURCES[ManagementEipAddress] = t.add_resource(EIP(
                        ManagementEipAddress,
                        DependsOn="AttachGateway",


                        Domain="vpc",
                    ))
                    RESOURCES[ManagementEipAssociation] = t.add_resource(EIPAssociation(
                        ManagementEipAssociation,
                        DependsOn="AttachGateway",


                        NetworkInterfaceId=Ref(ManagementInterface),
                        AllocationId=GetAtt(ManagementEipAddress, "AllocationId"),
                    ))
                else:
                    RESOURCES[ManagementEipAddress] = t.add_resource(EIP(
                        ManagementEipAddress,

                        Domain="vpc",
                    ))
                    RESOURCES[ManagementEipAssociation] = t.add_resource(EIPAssociation(
                        ManagementEipAssociation,

                        NetworkInterfaceId=Ref(ManagementInterface),
                        AllocationId=GetAtt(ManagementEipAddress, "AllocationId"),
                    ))

                if num_nics > 2:

                    InternalInterface = "Bigip" + str(BIGIP_INDEX + 1) + "InternalInterface"

                    RESOURCES[InternalInterface] = t.add_resource(NetworkInterface(
                        InternalInterface,
                        SubnetId=Ref(InternalSubnet),
                        GroupSet=[Ref(bigipInternalSecurityGroup)],



                        Description="Internal Interface for the BIG-IP",
                    ))
            # Build custom-config
            custom_config = [
                            "#!/bin/bash\n",
                            "### Add Supporting Config",
                            ]            
            if ha_type != "standalone":
                custom_config += [
                                    "HOSTNAME=`curl http://169.254.169.254/latest/meta-data/hostname`\n",
                                    "BIGIP_ADMIN_USERNAME='", Ref(adminUsername), "'\n", 
                                    "BIGIP_ADMIN_PASSWORD='", Ref(adminPassword), "'\n",                                    
                                 ]
                if license_type == "byol":
                    custom_config += [ "REGKEY=", Ref(licenseKey), "\n" ]
                elif license_type == "bigiq":
                    custom_config += [ 
                                        "BIGIQ_ADDRESS='", Ref(bigiqAddress), "'\n",
                                        "BIGIQ_USERNAME='", Ref(bigiqUsername), "'\n",
                                        "BIGIQ_PASSWORD='", Ref(bigiqPassword), "'\n",
                                        "BIGIQ_LICENSE_POOL_UUID='", Ref(bigiqLicensePoolUUID), "'\n"
                                    ]

                    if num_nics == 1:
                        custom_config += [ "BIGIP_DEVICE_ADDRESS='", Ref(ExternalSelfEipAddress),"'\n" ] 
                    if num_nics > 1:
                        custom_config += [ "BIGIP_DEVICE_ADDRESS='", Ref(ManagementEipAddress),"'\n" ] 


                if num_nics == 1:
                    custom_config += [ 
                                        "MANAGEMENT_GUI_PORT='", Ref(managementGuiPort), "'\n",  
                                        "GATEWAY_MAC=`ifconfig eth0 | egrep HWaddr | awk '{print tolower($5)}'`\n",
                                     ]

                if num_nics > 1:
                    custom_config += [ 
                                        "GATEWAY_MAC=`ifconfig eth1 | egrep HWaddr | awk '{print tolower($5)}'`\n",
                                     ]

                custom_config += [
                                    "GATEWAY_CIDR_BLOCK=`curl http://169.254.169.254/latest/meta-data/network/interfaces/macs/${GATEWAY_MAC}/subnet-ipv4-cidr-block`\n",
                                    "GATEWAY_NET=${GATEWAY_CIDR_BLOCK%/*}\n",
                                    "GATEWAY_PREFIX=${GATEWAY_CIDR_BLOCK#*/}\n",
                                    "GATEWAY=`echo ${GATEWAY_NET} | awk -F. '{ print $1\".\"$2\".\"$3\".\"$4+1 }'`\n",
                                    "VPC_CIDR_BLOCK=`curl http://169.254.169.254/latest/meta-data/network/interfaces/macs/${GATEWAY_MAC}/vpc-ipv4-cidr-block`\n",
                                    "VPC_NET=${VPC_CIDR_BLOCK%/*}\n",
                                    "VPC_PREFIX=${VPC_CIDR_BLOCK#*/}\n",
                                    "NAME_SERVER=`echo ${VPC_NET} | awk -F. '{ print $1\".\"$2\".\"$3\".\"$4+2 }'`\n", 
                                ]
                if num_nics > 1:
                    custom_config += [ 
                                    "MGMTIP='", GetAtt(ManagementInterface, "PrimaryPrivateIpAddress"), "'\n", 
                                    "EXTIP='", GetAtt(ExternalInterface, "PrimaryPrivateIpAddress"), "'\n", 
                                    "EXTPRIVIP='", Select("0", GetAtt(ExternalInterface, "SecondaryPrivateIpAddresses")), "'\n", 
                                    "EXTMASK='24'\n",
                                    ]
                if num_nics > 2:
                    custom_config += [ 
                                    "INTIP='",GetAtt(InternalInterface, "PrimaryPrivateIpAddress"),"'\n",
                                    "INTMASK='24'\n", 
                                   ]


            if stack == "full":
                custom_config +=  [              
                                    "POOLMEM='", GetAtt('Webserver','PrivateIp'), "'\n", 
                                    "POOLMEMPORT=80\n", 
                                    ]
    
                custom_config +=  [
                                    "APPNAME='demo-app-1'\n", 
                                    "VIRTUALSERVERPORT=80\n",
                                    "CRT='default.crt'\n", 
                                    "KEY='default.key'\n",
                                ]
            if ha_type != "standalone" and (BIGIP_INDEX + 1) == CLUSTER_SEED:
                custom_config +=  [
                                    "PEER_HOSTNAME='", GetAtt("Bigip" + str(BIGIP_INDEX + 2) + "Instance", "PrivateDnsName"), "'\n",
                                    "PEER_MGMTIP='", GetAtt("Bigip" + str(BIGIP_INDEX + 2) + "ManagementInterface", "PrimaryPrivateIpAddress"), "'\n",
                                    ]
                
                if num_nics > 1:
                    if ha_type == "across-az":
                        custom_config +=  [
                                            "PEER_EXTPRIVIP='", Select("0", GetAtt("Bigip" + str(BIGIP_INDEX + 2) + "subnet1" + "Az" + str(BIGIP_INDEX + 2) + "Interface", "SecondaryPrivateIpAddresses")), "'\n", 
                                            "VIPEIP='",Ref(VipEipAddress),"'\n",

                                            ]
                    if ha_type == "same-az":
                         custom_config +=  [
                                            "PEER_EXTPRIVIP='", Select("0", GetAtt("Bigip" + str(BIGIP_INDEX + 2) + "subnet1" + "Az1Interface", "SecondaryPrivateIpAddresses")), "'\n", 
                                            "VIPEIP='",Ref(VipEipAddress),"'\n",

                                            ]                   
            if aws_creds == True:
                custom_config +=  [
                                      "IAM_ACCESS_KEY='", Ref(iamAccessKey), "'\n",
                                      "IAM_SECRET_KEY='", Ref(iamSecretKey), "'\n",
                                    ]
            # build custom-confg.sh vars

            license_byol =  [ 
                                "--license ",
                                Ref(licenseKey),
                                # "nohup tcpdump -U -ni 0.0:nnn -s0 -c 10000 udp port 53 or host 104.219.104.132 -w /var/tmp/license-attempt.pcap &\n",
                                # "sleep 10\n",
                                # "LICENSE_RETURN=$( tmsh install /sys license registration-key \"${REGKEY}\")\n",
                                # "echo \"LICENSE_RETURN=${LICENSE_RETURN}\"\n",
                                # "pid=$(ps -e | pgrep tcpdump)\n",
                                # "echo killing pid=${pid}\n",
                                # "kill ${pid}\n", 
                            ]

            # License file downloaded remotely from https://cdn.f5.com/product/iapp/utils/license-from-bigiq.sh
            license_from_bigiq =  [
                                "echo 'start install biqiq license'\n",
                                ". /config/cloud/aws/license_from_bigiq.sh\n",
                                ]

            provision_asm = [
                                "echo 'provisioning asm'\n",
                                "tmsh modify /sys provision asm level nominal\n",
                                "checkretstatus='stop'\n",
                                "while [[ $checkretstatus != \"run\" ]]; do\n",
                                "     checkStatus\n",
                                "     if [[ $checkretstatus == \"restart\" ]]; then\n",
                                "         echo restarting\n",
                                "         tmsh modify /sys provision asm level none\n",
                                "         checkStatusnoret\n",
                                "         checkretstatus='stop'\n",
                                "         tmsh modify /sys provision asm level nominal\n",
                                "     fi\n",
                                "done\n",
                                "echo 'done provisioning asm'\n",
                            ]


            # TMSH CMD
            # tmsh create /sys application service HA_Across_AZs template f5.aws_advanced_ha.v1.2.0rc1 tables add { eip_mappings__mappings { column-names { eip az1_vip az2_vip } rows { { row { 52.27.196.185 /Common/10.0.1.100 /Common/10.0.11.100 } } } } } variables add { eip_mappings__inbound { value yes } }

            aws_advanced_ha_iapp_rest_payload = '{ \
    "name": "HA_Across_AZs", \
    "partition": "Common", \
    "inheritedDevicegroup": "true", \
    "inheritedTrafficGroup": "true", \
    "strictUpdates": "enabled", \
    "template": "/Common/f5.aws_advanced_ha.v1.2.0.tmpl", \
    "templateModified": "no", \
    "tables": [ \
        { \
            "name": "eip_mappings__mappings", \
            "columnNames": [ \
                "eip", \
                "az1_vip", \
                "az2_vip" \
            ], \
            "rows": [ \
                { \
                    "row": [ \
                        "${VIPEIP}", \
                        "/Common/${EXTPRIVIP}", \
                        "/Common/${PEER_EXTPRIVIP}" \
                    ] \
                }, \
            ] \
        }, \
        { \
            "name": "subnet_routes__cidr_blocks" \
        } \
    ], \
    "variables": [ \
        { \
            "encrypted": "no", \
            "name": "eip_mappings__inbound", \
            "value": "yes" \
        }, \
        { \
            "encrypted": "no", \
            "name": "options__advanced_mode", \
            "value": "yes" \
        }, \
        { \
            "encrypted": "no", \
            "name": "options__display_help", \
            "value": "hide" \
        }, \
        { \
            "encrypted": "no", \
            "name": "options__log_debug", \
            "value": "no" \
        }, \
        { \
            "encrypted": "no", \
            "name": "subnet_routes__route_management", \
            "value": "no" \
        } \
    ] \
}'

            # begin building custom-config.sh
            custom_sh = [
                            "#!/bin/bash\n",
                        ]
            sig_check1 = [
                            "cli script /Common/sigcheck {"
                        ]
            sig_check = [
                            "cli script /Common/verifyHash {",
                            "    proc script::run {} {",
                            "        if {[catch {",
                            "            set file_path [lindex $tmsh::argv 1]",
                            "            set expected_hash f5c4206c0b093fb2f3a6e16409610ec0300b509dee9157b2c4801f99e41d08b1b1d2b6a3c75c6a509daee77c3103403aa4c8ae47c4b232a6ec76b4663017b11c",
                            "            set computed_hash [lindex [exec /usr/bin/openssl dgst -r -sha512 $file_path] 0]",
                            "            if { $expected_hash eq $computed_hash } {",
                            "                exit 0",
                            "            }",
                            "            tmsh::log err {Hash does not match}",
                            "            exit 1",
                            "        }]} {",
                            "            tmsh::log err {Unexpected error in verifyHash}",
                            "            exit 1",
                            "        }",
                            "    }",
                            "    script-signature o4v4/Y2mV0cXV/eZefkq6wXlE5GCACYd6+HuN4ScfL/meD0Grw1aJxZGp9MAvv4Ik3IPIwS2n8WgvfG/cDKcwQHVMGFJN4kmN4tzhr9Zdf3879hKqJaqbLLkifDsYk8bX3ontvrqT7r7XKboBv2qygPaUrVZPtkxzbcAJ26ewIj9m+Rui2yp+uYskZAL0bAPi/g5KDTZvEz0rCtSSxOeVljk5lr6vA79HPCHfglCKucH1QnbcrGhpARcs+wiwCYC18yiKsOBl+BVRTQwXuQYs8RsNhCJ8bHQeM8dOHUZj5/1Exh0V6QOcqG8/6pMuSmXfduNKzmQQPyN+bO4ETQ03Q==",
                            "}"
                        ]
            cloudlibs_sh =  [
                                "#!/bin/bash",
                                "echo about to execute",
                                "checks=0",
                                "while [ $checks -lt 120 ]; do echo checking mcpd",
                                "    tmsh -a show sys mcp-state field-fmt | grep -q running",
                                "    if [ $? == 0 ]; then",
                                "        echo mcpd ready",
                                "        break",
                                "    fi",
                                "    echo mcpd not ready yet",
                                "    let checks=checks+1",
                                "    sleep 10",
                                "done",
                                "echo loading sigcheck script",
                                "tmsh load sys config merge file /config/sigcheck",
                                "if [ $? != 0 ]; then",
                                "    echo cannot validate signature of /config/sigcheck",
                                "    exit",
                                "fi",
                                "echo loaded sigcheck",
                                "echo verifying f5-cloud-libs.targ.gz",
                                "tmsh run cli script verifyHash /config/cloud/f5-cloud-libs.tar.gz",
                                "if [ $? != 0 ]; then",
                                "    echo f5-cloud-libs.tar.gz does not match signature f5-coud-libs.tar.gz.f5sig",
                                "    exit",
                                "fi",
                                "echo verified f5-cloud-libs.tar.gz",
                                "echo expanding f5-cloud-libs.tar.gz",
                                "tar xvfz /config/cloud/f5-cloud-libs.tar.gz -C /config/cloud/aws",
                                "cd /config/cloud/aws/f5-cloud-libs",
                                "touch /config/cloud/cloudLibsReady"
                            ]         
            waitthenrun_sh =    [
                                    "#!/bin/bash",
                                    "while true; do echo \"waiting for cloud libs install to complete\"",
                                    "    if [ -f /config/cloud/cloudLibsReady ]; then",
                                    "        break",
                                    "    else",
                                    "        sleep 10",
                                    "    fi",
                                    "done",
                                    "\"$@\""
                                ]
                                
            get_nameserver =    [
                                    "INTERFACE=$1",
                                    "INTERFACE_MAC=`ifconfig ${INTERFACE} | egrep HWaddr | awk '{print tolower($5)}'`",
                                    "INTERFACE_MAC=`ifconfig ${INTERFACE} | egrep HWaddr | awk '{print tolower($5)}'`",
                                    "VPC_CIDR_BLOCK=`curl -s http://169.254.169.254/latest/meta-data/network/interfaces/macs/${INTERFACE_MAC}/vpc-ipv4-cidr-block`",
                                    "VPC_NET=${VPC_CIDR_BLOCK%/*}",
                                    "NAME_SERVER=`echo ${VPC_NET} | awk -F. '{ printf \"%d.%d.%d.%d\", $1, $2, $3, $4+2 }'`",
                                    "echo $NAME_SERVER"
                                ]
            password_config =   [
                                Ref(adminPassword)
                                ]                    
            create_user =       [
                                    "#!/bin/bash",
                                    "PASSWORD=$(/bin/sed -e $'s:[\\'\"{};/|#\\x20\\\\\\\\]:\\\\\\\\&:g' < /config/cloud/aws/.adminPassword)",
                                    "if [ \"$1\" = admin ]; then",
                                    "    tmsh modify auth user \"$1\" password ${PASSWORD}",
                                    "else",
                                    "    tmsh create auth user \"$1\" password ${PASSWORD} shell bash partition-access replace-all-with { all-partitions { role admin } }",
                                    "fi"
                                ]
            admin_user  =   [
                                    "nohup /config/waitThenRun.sh",
                                    " f5-rest-node /config/cloud/aws/f5-cloud-libs/scripts/runScript.js",
                            ]
            if num_nics == 1:
                admin_user +=   [
                                    " --wait-for 1_NIC_SETUP_DONE",
                                ]
            admin_user +=   [    
                                    " --signal ADMIN_CREATED",
                                    " --file /config/cloud/aws/createUser.sh",
                                    " --cl-args ", Ref(adminUsername),
                                    " --log-level debug",
                                    " -o /var/log/createUser.log",
                                    " > /var/log/cloudlibs-install.log 2> /var/log/cloudlibs-install.log < /dev/null &"  
                            ]    
            unpack_libs =       [
                                    "nohup /config/installCloudLibs.sh",
                                    "> /var/log/cloudlibs-install.log 2> /var/log/cloudlibs-install.log < /dev/null &"
                                ]
               
            onboard_BIG_IP =    [
                                ]
            one_nic_setup =     [
                                ]
            cluster_BIG_IP=     [
                                ]                                
            custom_command =   [
                                    "nohup /config/waitThenRun.sh",
                                    "f5-rest-node /config/cloud/aws/f5-cloud-libs/scripts/runScript.js",
                                    "--file /config/cloud/aws/custom-config.sh",
                                    "--cwd /config/cloud/aws",
                                    "-o /var/log/custom-config.log",
                                    "--log-level debug",
                                    "--wait-for ONBOARD_DONE",
                                    "> /var/log/cloudlibs-install.log 2> /var/log/cloudlibs-install.log < /dev/null &"
                                ]
            if ha_type != "standalone":
                custom_sh +=    [

                                ]
            # Global Settings
            custom_sh += [
                            "date\n",
                            "echo 'starting tmsh config'\n",
                         ]
            if num_nics == 1:
                one_nic_setup += [
                                    "nohup /config/waitThenRun.sh",
                                    "f5-rest-node /config/cloud/aws/f5-cloud-libs/scripts/runScript.js",
                                    "--file /config/cloud/aws/f5-cloud-libs/scripts/aws/1nicSetup.sh",
                                    "--cwd /config/cloud/aws/f5-cloud-libs/scripts/aws",
                                    "--log-level debug",
                                    "-o /var/log/1nicSetup.log",
                                    "--signal 1_NIC_SETUP_DONE",
                                    "> /var/log/cloudlibs-install.log 2> /var/log/cloudlibs-install.log < /dev/null &"
                                 ]
                   
                onboard_BIG_IP += [
                                    "NAME_SERVER=`/config/getNameServer.sh eth0`;",
                                    "nohup /config/waitThenRun.sh",
                                    "f5-rest-node /config/cloud/aws/f5-cloud-libs/scripts/onboard.js",
                                    "--ssl-port ", Ref(managementGuiPort),
                                  ]
            if num_nics > 1:
                onboard_BIG_IP += [
                                    "NAME_SERVER=`/config/getNameServer.sh eth1`;",
                                    "nohup /config/waitThenRun.sh",
                                    "f5-rest-node /config/cloud/aws/f5-cloud-libs/scripts/onboard.js",
                                  ]
            onboard_BIG_IP += [
                               "--wait-for ADMIN_CREATED",
                               "-o /var/log/onboard.log",
                               "--log-level debug",
                               "--no-reboot",
                               "--host localhost",
                               "--user ", Ref(adminUsername),
                               "--password-url file:///config/cloud/aws/.adminPassword",
                               "--hostname `curl http://169.254.169.254/latest/meta-data/hostname`",
                               "--ntp 0.us.pool.ntp.org",
                               "--ntp 1.us.pool.ntp.org",
                               "--tz UTC",
                               "--dns ${NAME_SERVER}",
                               "--module ltm:nominal",
                            ]
            if aws_creds:
                custom_sh += [
                                "tmsh modify sys global-settings aws-access-key", Ref(iamAccessKey), "\n",
                                "tmsh modify sys global-settings aws-secret-key", Ref(iamSecretKey), "\n",
                                ]   
            if num_nics == 1:
                # Sync and Failover ( UDP 1026 and TCP 4353 already included in self-allow defaults )
                if 'waf' in components:
                    custom_sh +=  [ 
                                    "tmsh modify net self-allow defaults add { tcp:6123 tcp:6124 tcp:6125 tcp:6126 tcp:6127 tcp:6128 }\n",
                                    ]
            # Network Settings
            if num_nics > 1:
                custom_sh +=  [ 
                                "GATEWAY_MAC=`ifconfig eth1 | egrep HWaddr | awk '{print tolower($5)}'`\n",
                                "GATEWAY_CIDR_BLOCK=`curl http://169.254.169.254/latest/meta-data/network/interfaces/macs/${GATEWAY_MAC}/subnet-ipv4-cidr-block`\n",
                                "GATEWAY_NET=${GATEWAY_CIDR_BLOCK%/*}\n",
                                "GATEWAY_PREFIX=${GATEWAY_CIDR_BLOCK#*/}\n",
                                "GATEWAY=`echo ${GATEWAY_NET} | awk -F. '{ print $1\".\"$2\".\"$3\".\"$4+1 }'`\n",
                                "EXTIP='", GetAtt(ExternalInterface, "PrimaryPrivateIpAddress"), "'\n", 
                                "EXTPRIVIP='", Select("0", GetAtt(ExternalInterface, "SecondaryPrivateIpAddresses")), "'\n", 
                                "EXTMASK=${GATEWAY_PREFIX}\n",
                                "tmsh create net vlan external interfaces add { 1.1 } \n",
                                ]
                if ha_type == "standalone":
                    if 'waf' not in components:
                        custom_sh +=  [ 
                                        "tmsh create net self ${EXTIP}/${EXTMASK} vlan external allow-service add { tcp:4353 }\n",
                                        ]
                    if 'waf' in components:                    
                        custom_sh +=  [ 
                                        "tmsh create net self ${EXTIP}/${EXTMASK} vlan external allow-service add { tcp:6123 tcp:6124 tcp:6125 tcp:6126 tcp:6127 tcp:6128 }\n",
                                        ]
                if ha_type != "standalone":
                    if 'waf' not in components:
                        custom_sh +=  [ 
                                        "tmsh create net self ${EXTIP}/${EXTMASK} vlan external allow-service add { tcp:4353 udp:1026 }\n",
                                        ]
                    if 'waf' in components:
                        custom_sh +=  [ 
                                        "tmsh create net self ${EXTIP}/${EXTMASK} vlan external allow-service add { tcp:4353 udp:1026 tcp:6123 tcp:6124 tcp:6125 tcp:6126 tcp:6127 tcp:6128 }\n",
                                        ]
            if num_nics > 2:
                custom_sh +=  [ 
                                "GATEWAY_MAC2=`ifconfig eth2 | egrep HWaddr | awk '{print tolower($5)}'`\n",
                                "GATEWAY_CIDR_BLOCK2=`curl http://169.254.169.254/latest/meta-data/network/interfaces/macs/${GATEWAY_MAC2}/subnet-ipv4-cidr-block`\n",
                                "GATEWAY_PREFIX2=${GATEWAY_CIDR_BLOCK2#*/}\n",
                                "INTIP='",GetAtt(InternalInterface, "PrimaryPrivateIpAddress"),"'\n",
                                "INTMASK=${GATEWAY_PREFIX2}\n", 
                                "tmsh create net vlan internal interfaces add { 1.2 } \n",
                                "tmsh create net self ${INTIP}/${INTMASK} vlan internal allow-service default\n",
                                ]
            # Set Gateway
            if ha_type == "across-az":
                cluster_BIG_IP +=   [
                                 
                                    ]
                custom_sh +=  [                  
                                    "tmsh create sys folder /LOCAL_ONLY device-group none traffic-group traffic-group-local-only\n",
                                    "tmsh create net route /LOCAL_ONLY/default network default gw ${GATEWAY}\n",
                                ]
            else:
                if num_nics > 1:
                    custom_sh +=  [
                                        "tmsh create net route default gw ${GATEWAY}\n",
                                    ]
            # Disable DHCP if clustering. 
            if ha_type != "standalone":
                custom_sh += [ 
                                    "HOSTNAME=`curl http://169.254.169.254/latest/meta-data/hostname`\n",
                                    "tmsh mv cm device bigip1 ${HOSTNAME}\n",
                                    "tmsh modify sys db dhclient.mgmt { value disable }\n",
                                ] 
                if num_nics == 1:
                    custom_sh += [
                                    "MGMT_ADDR=$(tmsh list sys management-ip | awk '/management-ip/ {print $3}')\n",
                                    "MGMT_IP=${MGMT_ADDR%/*}\n",
                                    "tmsh modify cm device ${HOSTNAME} configsync-ip ${MGMT_IP} }\n", 
                                   ]
                else:
                    # For simplicity, putting all clustering endpoints on external subnet
                    custom_sh += [
                                    "tmsh modify cm device ${HOSTNAME} configsync-ip ${EXTIP} unicast-address { { effective-ip ${EXTIP} effective-port 1026 ip ${EXTIP} } }\n", 
                                   ]
            # License Device
            if license_type == "byol":
                onboard_BIG_IP += license_byol
            elif license_type == "bigiq":
                custom_sh += license_from_bigiq
            # Wait until licensing finishes
            if license_type == "hourly":
                custom_sh +=    [
                                ]
            # Provision Modules
            if 'waf' in components:
               onboard_BIG_IP += [ 
                                    "--module asm:nominal",
                                 ]
            onboard_BIG_IP += [ 
                "--ping",
                "> /var/log/cloudlibs-install.log 2> /var/log/cloudlibs-install.log < /dev/null &"
            ]
            # Cluster Devices if Cluster Seed
            if ha_type != "standalone" and (BIGIP_INDEX + 1) == CLUSTER_SEED:
                custom_sh +=  [
                                "echo 'sleeping additional 180 secs to wait for peer to boot'\n",
                                "sleep 180\n",
                                "PEER_HOSTNAME='", GetAtt("Bigip" + str(BIGIP_INDEX + 2) + "Instance", "PrivateDnsName"), "'\n",
                                "PEER_MGMTIP='", GetAtt("Bigip" + str(BIGIP_INDEX + 2) + "ManagementInterface", "PrimaryPrivateIpAddress"), "'\n",
                                "USERNAME=", Ref(adminUsername), "\n",
                                "PASSWORD=", Ref(adminPassword), "\n",
                                "tmsh modify cm trust-domain Root ca-devices add { ${PEER_MGMTIP} } name ${PEER_HOSTNAME} username \"${USERNAME}\" password \"${PASSWORD}\"\n",    
                                "tmsh create cm device-group across_az_failover_group type sync-failover devices add { ${HOSTNAME} ${PEER_HOSTNAME} } auto-sync enabled\n",
                                "sleep 10\n",
                                "tmsh run cm config-sync to-group across_az_failover_group\n", 
                                ]
            if ha_type == "standalone" or (BIGIP_INDEX + 1) == CLUSTER_SEED:
                if stack != "existing": 
                    #Add Pool
                    custom_sh +=    [
                                        "tmsh create ltm pool ${APPNAME}-pool members add { ${POOLMEM}:${POOLMEMPORT} } monitor http\n",
                                    ]

                    # Add virtual service with simple URI-Routing ltm policy
                    if 'waf' not in components:
                        custom_sh +=    [
                                            "tmsh create ltm policy uri-routing-policy controls add { forwarding } requires add { http } strategy first-match legacy\n",
                                            "tmsh modify ltm policy uri-routing-policy rules add { service1.example.com { conditions add { 0 { http-uri host values { service1.example.com } } } actions add { 0 { forward select pool ${APPNAME}-pool } } ordinal 1 } }\n",
                                            "tmsh modify ltm policy uri-routing-policy rules add { service2.example.com { conditions add { 0 { http-uri host values { service2.example.com } } } actions add { 0 { forward select pool ${APPNAME}-pool } } ordinal 2 } }\n",
                                            "tmsh modify ltm policy uri-routing-policy rules add { apiv2 { conditions add { 0 { http-uri path starts-with values { /apiv2 } } } actions add { 0 { forward select pool ${APPNAME}-pool } } ordinal 3 } }\n",
                                        ]

                        if ha_type != "across-az":
                            if num_nics == 1:
                                custom_sh +=    [
                                                    "tmsh create ltm virtual /Common/${APPNAME}-${VIRTUALSERVERPORT} { destination 0.0.0.0:${VIRTUALSERVERPORT} mask any ip-protocol tcp pool /Common/${APPNAME}-pool policies replace-all-with { uri-routing-policy { } } profiles replace-all-with { tcp { } http { } }  source 0.0.0.0/0 source-address-translation { type automap } translate-address enabled translate-port enabled }\n",
                                                ]
                            if num_nics > 1:
                                custom_sh +=    [
                                                    "tmsh create ltm virtual /Common/${APPNAME}-${VIRTUALSERVERPORT} { destination ${EXTPRIVIP}:${VIRTUALSERVERPORT} mask 255.255.255.255 ip-protocol tcp pool /Common/${APPNAME}-pool policies replace-all-with { uri-routing-policy { } } profiles replace-all-with { tcp { } http { } }  source 0.0.0.0/0 source-address-translation { type automap } translate-address enabled translate-port enabled }\n",
                                                ]
                        if ha_type == "across-az":                      
                            custom_sh +=    [
                                                "tmsh create ltm virtual /Common/AZ1-${APPNAME}-${VIRTUALSERVERPORT} { destination ${EXTPRIVIP}:${VIRTUALSERVERPORT} mask 255.255.255.255 ip-protocol tcp pool /Common/${APPNAME}-pool policies replace-all-with { uri-routing-policy { } } profiles replace-all-with { tcp { } http { } }  source 0.0.0.0/0 source-address-translation { type automap } translate-address enabled translate-port enabled }\n",
                                                "tmsh create ltm virtual /Common/AZ2-${APPNAME}-${VIRTUALSERVERPORT} { destination ${PEER_EXTPRIVIP}:${VIRTUALSERVERPORT} mask 255.255.255.255 ip-protocol tcp pool /Common/${APPNAME}-pool policies replace-all-with { uri-routing-policy { } } profiles replace-all-with { tcp { } http { } }  source 0.0.0.0/0 source-address-translation { type automap } translate-address enabled translate-port enabled }\n",
                                                "tmsh modify ltm virtual-address ${EXTPRIVIP} traffic-group none\n",                                            
                                            ]
                if 'waf' in components:
                    # 12.1.0 requires "first match legacy"
                    custom_sh += [
                                    "curl -o /home/admin/asm-policy-linux-high.xml http://cdn.f5.com/product/templates/utils/asm-policy-linux-high.xml \n",
                                    "tmsh load asm policy file /home/admin/asm-policy-linux-high.xml\n",
                                    "# modify asm policy names below (ex. /Common/linux-high) to match name in xml\n",
                                    "tmsh modify asm policy /Common/linux-high active\n",
                                    "tmsh create ltm policy app-ltm-policy strategy first-match legacy\n",
                                    "tmsh modify ltm policy app-ltm-policy controls add { asm }\n",
                                    "tmsh modify ltm policy app-ltm-policy rules add { associate-asm-policy { actions replace-all-with { 0 { asm request enable policy /Common/linux-high } } } }\n",
                                 ]
                    if stack != "existing":
                        if ha_type != "across-az":
                            if num_nics == 1:
                                custom_sh +=    [
                                                    "tmsh create ltm virtual /Common/${APPNAME}-${VIRTUALSERVERPORT} { destination 0.0.0.0:${VIRTUALSERVERPORT} mask any ip-protocol tcp policies replace-all-with { app-ltm-policy { } } pool /Common/${APPNAME}-pool profiles replace-all-with { http { } tcp { } websecurity { } } security-log-profiles replace-all-with { \"Log illegal requests\" } source 0.0.0.0/0 source-address-translation { type automap } translate-address enabled translate-port enabled}\n",
                                                ]

                            if num_nics > 1:
                                custom_sh +=    [
                                                    "tmsh create ltm virtual /Common/${APPNAME}-${VIRTUALSERVERPORT} { destination ${EXTPRIVIP}:${VIRTUALSERVERPORT} mask 255.255.255.255 ip-protocol tcp policies replace-all-with { app-ltm-policy { } } pool /Common/${APPNAME}-pool profiles replace-all-with { http { } tcp { } websecurity { } } security-log-profiles replace-all-with { \"Log illegal requests\" } source 0.0.0.0/0 source-address-translation { type automap } translate-address enabled translate-port enabled}\n",
                                                ]
                        if ha_type == "across-az":                      
                            custom_sh +=    [
                                                "tmsh create ltm virtual /Common/AZ1-${APPNAME}-${VIRTUALSERVERPORT} { destination ${EXTPRIVIP}:${VIRTUALSERVERPORT} mask 255.255.255.255 ip-protocol tcp policies replace-all-with { app-ltm-policy { } } pool /Common/${APPNAME}-pool profiles replace-all-with { http { } tcp { } websecurity { } } security-log-profiles replace-all-with { \"Log illegal requests\" } source 0.0.0.0/0 source-address-translation { type automap } translate-address enabled translate-port enabled}\n",
                                                "tmsh create ltm virtual /Common/AZ2-${APPNAME}-${VIRTUALSERVERPORT} { destination ${PEER_EXTPRIVIP}:${VIRTUALSERVERPORT} mask 255.255.255.255 ip-protocol tcp policies replace-all-with { app-ltm-policy { } } pool /Common/${APPNAME}-pool profiles replace-all-with { http { } tcp { } websecurity { } } security-log-profiles replace-all-with { \"Log illegal requests\" } source 0.0.0.0/0 source-address-translation { type automap } translate-address enabled translate-port enabled}\n",
                                                "tmsh modify ltm virtual-address ${EXTPRIVIP} traffic-group none\n",
                                                "tmsh modify ltm virtual-address ${PEER_EXTPRIVIP} traffic-group none\n",
                                            ]
                if ha_type == "across-az":
                    custom_sh +=    [
                                    "curl -sSk -o /config/cloud/aws/f5.aws_advanced_ha.v1.2.0rc1.tmpl --max-time 15 https://cdn.f5.com/product/templates/f5.aws_advanced_ha.v1.2.0rc1.tmpl\n",
                                    "tmsh load sys application template /config/cloud/aws/f5.aws_advanced_ha.v1.2.0rc1.tmpl\n",
                                    "tmsh create /sys application service HA_Across_AZs template f5.aws_advanced_ha.v1.2.0rc1 tables add { eip_mappings__mappings { column-names { eip az1_vip az2_vip } rows { { row { ${VIPEIP} /Common/${EXTPRIVIP} /Common/${PEER_EXTPRIVIP} } } } } } variables add { eip_mappings__inbound { value yes } }\n",
                                    "tmsh modify sys application service HA_Across_AZs.app/HA_Across_AZs execute-action definition\n",
                                    "tmsh run cm config-sync to-group across_az_failover_group\n",
                                    "sleep 15\n",
                                    "curl -sSk -u \"${BIGIP_ADMIN_USERNAME}\":\"${BIGIP_ADMIN_PASSWORD}\" -H 'Content-Type: application/json' -X PATCH -d '{\"execute-action\":\"definition\"}' https://${PEER_MGMTIP}/mgmt/tm/sys/application/service/~Common~HA_Across_AZs.app~HA_Across_AZs\n",
                                    ]
            # If ASM, Need to use overwite Config (SOL16509 / BZID: 487538 )
            if ha_type != "standalone" and (BIGIP_INDEX + 1) == CLUSTER_SEED:
                if 'waf' in components:
                    custom_sh += [
                                            "tmsh modify cm device-group datasync-global-dg devices modify { ${HOSTNAME} { set-sync-leader } }\n", 
                                            "tmsh run cm config-sync to-group datasync-global-dg\n",
                                    ]
            if license_type == "byol":                
                custom_sh += [
                                    "tmsh save /sys config\n",
                                    "date\n",
                                    "### START CUSTOM TMSH CONFIGURTION\n",
                                    "### END CUSTOM TMSH CONFIGURATION"
                               ]
            else:
                custom_sh += [
                                    "rm /config/cloud/aws/.adminPassword\n",
                                    "tmsh save /sys config\n",
                                    "date\n",
                                    "### START CUSTOM TMSH CONFIGURTION\n",
                                    "### END CUSTOM TMSH CONFIGURATION"
                                    
                               ]             

            if license_type == "bigiq":
                metadata = Metadata(
                        Init({
                            'config': InitConfig(
                                files=InitFiles(
                                    {
                                        '/config/cloud/f5-cloud-libs.tar.gz': InitFile(
                                            source='https://raw.githubusercontent.com/F5Networks/f5-cloud-libs/v2.0.0/dist/f5-cloud-libs.tar.gz',
                                            mode='000755',
                                            owner='root',
                                            group='root'
                                        ),
                                        '/config/cloud/aws/custom.config': InitFile(
                                            content=Join('', custom_config ),
                                            mode='000755',
                                            owner='root',
                                            group='root'
                                        ),
                                        '/config/cloud/aws/firstrun.utils': InitFile(
                                            source='http://cdn.f5.com/product/templates/utils/firstrun.utils',
                                            mode='000755',
                                            owner='root',
                                            group='root'
                                        ),
                                        '/config/cloud/aws/license_from_bigiq.sh': InitFile(
                                            source='http://cdn.f5.com/product/templates/utils/license_from_bigiq_v5.0.sh',
                                            mode='000755',
                                            owner='root',
                                            group='root'
                                        ),
                                        '/config/cloud/aws/remove_license_from_bigiq.sh': InitFile(
                                            source='http://cdn.f5.com/product/templates/utils/remove_license_from_bigiq_v5.0.sh',
                                            mode='000755',
                                            owner='root',
                                            group='root'
                                        ),
                                        '/config/cloud/aws/custom-config.sh': InitFile(
                                            content=Join('', custom_sh ),
                                            mode='000755',
                                            owner='root',
                                            group='root'
                                        )
                                    } 
                                ),
                                commands={
                                            "001-unpack-libs": {
                                                "command": { "Fn::Join" : [ " ", unpack_libs
                                                                          ]
                                                }
                                            },
                                            "002-1nic-setup": {
                                                "command": { 
                                                    "Fn::Join" : [ " ", one_nic_setup
                                                                 ]
                                                }
                                            },
                                            "003-onboard-BIG-IP": {
                                                "command": { "Fn::Join" : [ " ", onboard_BIG_IP
                                                                          ]
                                                }
                                            },
                                            "005-custom-config": {
                                                "command": { 
                                                    "Fn::Join" : [ " ", custom_command
                                                                 ]
                                                }
                                            },
                                }
                            ) 
                        })
                    )
            else:
             
                metadata = Metadata(
                        Init({
                            'config': InitConfig(
                                files=InitFiles(
                                    {
                                        '/config/cloud/f5-cloud-libs.tar.gz': InitFile(
                                            source='https://raw.githubusercontent.com/F5Networks/f5-cloud-libs/v2.0.1/dist/f5-cloud-libs.tar.gz',
                                            mode='000755',
                                            owner='root',
                                            group='root'
                                        ),
                                        '/config/sigcheck': InitFile(
                                            content=Join('\n', sig_check ),
                                            mode='000755',
                                            owner='root',
                                            group='root'
                                        ),
                                        '/config/installCloudLibs.sh': InitFile(
                                            content=Join('\n', cloudlibs_sh ),
                                            mode='000755',
                                            owner='root',
                                            group='root'
                                        ),
                                        '/config/waitThenRun.sh': InitFile(
                                            content=Join('\n', waitthenrun_sh ),
                                            mode='000755',
                                            owner='root',
                                            group='root'
                                        ),
                                        '/config/getNameServer.sh': InitFile(
                                            content=Join('\n', get_nameserver ),
                                            mode='000755',
                                            owner='root',
                                            group='root'
                                        ),
                                        '/config/cloud/aws/createUser.sh': InitFile(
                                            content=Join('\n', create_user ),
                                            mode='000755',
                                            owner='root',
                                            group='root'
                                        ),
                                        '/config/cloud/aws/.adminPassword': InitFile(
                                            content=Ref(adminPassword),
                                            mode='000755',
                                            owner='root',
                                            group='root'
                                        ),
                                        '/config/cloud/aws/custom-config.sh': InitFile(
                                            content=Join('', custom_sh ),
                                            mode='000755',
                                            owner='root',
                                            group='root'
                                        )
                                    } 
                                ),
                                commands={  
                                            "001-disable-1nicautoconfig": {
                                                "command": "/usr/bin/setdb provision.1nicautoconfig disable"
                                            },                                            
                                            "002-install-libs": {
                                                "command": { "Fn::Join" : [ " ", unpack_libs
                                                                          ]
                                                }
                                            },
                                            "003-1nic-setup": {
                                                "command": { 
                                                    "Fn::Join" : [ " ", one_nic_setup
                                                                 ]
                                                }
                                            },
                                            "004-create-admin-user": {
                                                "command": { 
                                                    "Fn::Join" : [ "", admin_user
                                                                 ]
                                                }
                                            },
                                            "005-onboard-BIG-IP": {
                                                "command": { 
                                                    "Fn::Join" : [ " ", onboard_BIG_IP
                                                                 ]
                                                }
                                            },
                                            "006-custom-config": {
                                                "command": { 
                                                    "Fn::Join" : [ " ", custom_command
                                                                 ]
                                                }
                                            },
                                }
                            ) 
                        })
                    )
            NetworkInterfaces = []
            if num_nics == 1:
                NetworkInterfaces = [
                    NetworkInterfaceProperty(
                        DeviceIndex="0",
                        NetworkInterfaceId=Ref(ExternalInterface),
                        Description="Public or External Interface",
                    ),
                ]
            if num_nics == 2:  
                NetworkInterfaces = [
                    NetworkInterfaceProperty(
                        DeviceIndex="0",
                        NetworkInterfaceId=Ref(ManagementInterface),
                        Description="Management Interface",
                    ),
                    NetworkInterfaceProperty(
                        DeviceIndex="1",
                        NetworkInterfaceId=Ref(ExternalInterface),
                        Description="Public or External Interface",
                    ),    
                ]
            if num_nics == 3:  
                NetworkInterfaces = [
                    NetworkInterfaceProperty(
                        DeviceIndex="0",
                        NetworkInterfaceId=Ref(ManagementInterface),
                        Description="Management Interface",
                    ),
                    NetworkInterfaceProperty(
                        DeviceIndex="1",
                        NetworkInterfaceId=Ref(ExternalInterface),
                        Description="Public or External Interface",
                    ),
                    NetworkInterfaceProperty(
                        DeviceIndex="2",
                        NetworkInterfaceId=Ref(InternalInterface),
                        Description="Private or Internal Interface",
                    ), 
                ]
            if ha_type != "standalone" and (BIGIP_INDEX + 1) == CLUSTER_SEED:
                RESOURCES[BigipInstance] = t.add_resource(Instance(
                    BigipInstance,
                    DependsOn="Bigip" + str(BIGIP_INDEX + 2) + "Instance",
                    Metadata=metadata,
                    UserData=Base64(Join("", ["#!/bin/bash\n", "/opt/aws/apitools/cfn-init-1.4-0.amzn1/bin/cfn-init -v -s ", Ref("AWS::StackId"), " -r ", BigipInstance , " --region ", Ref("AWS::Region"), "\n"])),
                    Tags=Tags(
                        Name=Join("", ["Big-IP: ", Ref("AWS::StackName")] ),
                        Application=Ref(application),
                        Environment=Ref(environment),
                        Group=Ref(group),
                        Owner=Ref(owner),
                        Costcenter=Ref(costcenter),
                    ),
                    ImageId=FindInMap("BigipRegionMap", Ref("AWS::Region"), Ref(imageName)),
                    KeyName=Ref(sshKey),
                    InstanceType=Ref(instanceType),
                    NetworkInterfaces=NetworkInterfaces
                ))
            else:
                RESOURCES[BigipInstance] = t.add_resource(Instance(
                    BigipInstance,
                    Metadata=metadata,
                    UserData=Base64(Join("", ["#!/bin/bash\n", "/opt/aws/apitools/cfn-init-1.4-0.amzn1/bin/cfn-init -v -s ", Ref("AWS::StackId"), " -r ", BigipInstance , " --region ", Ref("AWS::Region"), "\n"])),
                    Tags=Tags(
                        Name=Join("", ["Big-IP: ", Ref("AWS::StackName")] ),
                        Application=Ref(application),
                        Environment=Ref(environment),
                        Group=Ref(group),
                        Owner=Ref(owner),
                        Costcenter=Ref(costcenter),
                    ),
                    ImageId=FindInMap("BigipRegionMap", Ref("AWS::Region"), Ref(imageName)),
                    KeyName=Ref(sshKey),
                    InstanceType=Ref(instanceType),
                    NetworkInterfaces=NetworkInterfaces
                ))

    ### BEGIN OUTPUT
    if network == True:
        Vpc = t.add_output(Output(
            "Vpc",

            Description="VPC ID",
            Value=Ref(Vpc),
        ))

        DnsServers = t.add_output(Output(
            "DnsServers",

            Description="DNS server for VPC",
            Value="10.0.0.2",
        ))

        for INDEX in range(num_azs):
            ApplicationSubnet = "Az" + str(INDEX + 1) + "ApplicationSubnet"
            OUTPUTS[ApplicationSubnet] = t.add_output(Output(
                ApplicationSubnet,
                Description="Az" + str(INDEX + 1) +  "Application Subnet Id",
                Value=Ref(ApplicationSubnet),
            ))

        for INDEX in range(num_azs):
            ExternalSubnet = "subnet1" + "Az" + str(INDEX + 1)

            OUTPUTS[ExternalSubnet] = t.add_output(Output(
                ExternalSubnet,

                Description="Az" + str(INDEX + 1) +  "External Subnet Id",
                Value=Ref(ExternalSubnet),

            ))

        if num_nics > 1:
            for INDEX in range(num_azs):
                managementSubnet = "managementSubnet" + "Az" + str(INDEX + 1)

                OUTPUTS[managementSubnet] = t.add_output(Output(
                    managementSubnet,

                    Description="Az" + str(INDEX + 1) +  "Management Subnet Id",
                    Value=Ref(managementSubnet),

                ))

        if num_nics > 2:
            for INDEX in range(num_azs):
                InternalSubnet = "subnet2" + "Az" + str(INDEX + 1)

                OUTPUTS[InternalSubnet] = t.add_output(Output(
                    InternalSubnet,

                    Description="Az" + str(INDEX + 1) +  "Internal Subnet Id",
                    Value=Ref(InternalSubnet),

                ))

    if security_groups == True:

        bigipExternalSecurityGroup = t.add_output(Output(
            "bigipExternalSecurityGroup",

            Description="Public or External Security Group",
            Value=Ref(bigipExternalSecurityGroup),

        ))

        if num_nics > 1:
            bigipManagementSecurityGroup = t.add_output(Output(
                "bigipManagementSecurityGroup",


                Description="Management Security Group",
                Value=Ref(bigipManagementSecurityGroup),

            ))

        if num_nics > 2:
            bigipInternalSecurityGroup = t.add_output(Output(
                "bigipInternalSecurityGroup",

                Description="Private or Internal Security Group",
                Value=Ref(bigipInternalSecurityGroup),

            ))


    if bigip == True:

        for BIGIP_INDEX in range(num_bigips):
            if ha_type == "across-az":
                ExternalInterface = "Bigip" + str(BIGIP_INDEX + 1) + "subnet1" + "Az" + str(BIGIP_INDEX + 1) + "Interface"
                ExternalSelfEipAddress = "Bigip" + str(BIGIP_INDEX + 1) + "subnet1" + "Az" + str(BIGIP_INDEX + 1) + "SelfEipAddress"
                ExternalSelfEipAssociation = "Bigip" + str(BIGIP_INDEX + 1) + "subnet1" + "Az" + str(BIGIP_INDEX + 1) + "SelfEipAssociation"
            if ha_type == "same-az":
                ExternalInterface = "Bigip" + str(BIGIP_INDEX + 1) + "subnet1" + "Az1Interface"
                ExternalSelfEipAddress = "Bigip" + str(BIGIP_INDEX + 1) + "subnet1" + "Az1SelfEipAddress"
                ExternalSelfEipAssociation = "Bigip" + str(BIGIP_INDEX + 1) + "subnet1" + "Az1SelfEipAssociation"            
            ExternalInterfacePrivateIp = "Bigip" + str(BIGIP_INDEX + 1) + "ExternalInterfacePrivateIp"
            BigipInstance = "Bigip" + str(BIGIP_INDEX + 1) + "Instance"
            BigipInstanceId = "Bigip" + str(BIGIP_INDEX + 1) + "InstanceId"
            BigipUrl = "Bigip" + str(BIGIP_INDEX + 1) + "Url"
            AvailabilityZone = "availabilityZone" + str(BIGIP_INDEX + 1)

            OUTPUTS[BigipInstanceId] = t.add_output(Output(
                BigipInstanceId,
                Description="Instance Id of BIG-IP in Amazon",
                Value=Ref(BigipInstance),
            ))

            OUTPUTS[AvailabilityZone] = t.add_output(Output(
                AvailabilityZone,
                Description="Availability Zone",
                Value=GetAtt(BigipInstance, "AvailabilityZone"),
            ))

            OUTPUTS[ExternalInterface] = t.add_output(Output(
                ExternalInterface,
                Description="External interface Id on BIG-IP",
                Value=Ref(ExternalInterface),
            ))

            OUTPUTS[ExternalInterfacePrivateIp] = t.add_output(Output(
                ExternalInterfacePrivateIp,
                Description="Internally routable IP of the public interface on BIG-IP",
                Value=GetAtt(ExternalInterface, "PrimaryPrivateIpAddress"),
            ))

            OUTPUTS[ExternalSelfEipAddress] = t.add_output(Output(
                ExternalSelfEipAddress,
                Description="IP Address of the External interface attached to BIG-IP",
                Value=Ref(ExternalSelfEipAddress),
            ))

            if num_nics == 1:

                VipEipAddress = "Bigip" + str(BIGIP_INDEX + 1) + "VipEipAddress"

                OUTPUTS[BigipUrl] = t.add_output(Output(
                    BigipUrl,

                    Description="BIG-IP Management GUI",
                    Value=Join("", [ "https://", GetAtt(BigipInstance, "PublicIp"), ":", Ref(managementGuiPort) ]),
                ))

                OUTPUTS[VipEipAddress] = t.add_output(Output(
                    VipEipAddress,

                    Description="EIP address for VIP",
                    Value=Join("", ["http://", GetAtt(BigipInstance, "PublicIp") , ":80"]),
                ))


            if num_nics > 1:


                ManagementInterface = "Bigip" + str(BIGIP_INDEX + 1) + "ManagementInterface"
                ManagementInterfacePrivateIp = "Bigip" + str(BIGIP_INDEX + 1) + "ManagementInterfacePrivateIp"
                ManagementEipAddress = "Bigip" + str(BIGIP_INDEX + 1) + "ManagementEipAddress"
                VipPrivateIp = "Bigip" + str(BIGIP_INDEX + 1) + "VipPrivateIp"
                VipEipAddress = "Bigip" + str(BIGIP_INDEX + 1) + "VipEipAddress"

                OUTPUTS[BigipUrl] = t.add_output(Output(
                    BigipUrl,

                    Description="BIG-IP Management GUI",
                    Value=Join("", ["https://", GetAtt(BigipInstance, "PublicIp")]),
                ))

                OUTPUTS[ManagementInterface] = t.add_output(Output(
                    ManagementInterface,

                    Description="Management interface ID on BIG-IP",
                    Value=Ref(ManagementInterface),

                ))

                OUTPUTS[ManagementInterfacePrivateIp] = t.add_output(Output(
                    ManagementInterfacePrivateIp,

                    Description="Internally routable IP of the management interface on BIG-IP",
                    Value=GetAtt(ManagementInterface, "PrimaryPrivateIpAddress"),
                ))

                OUTPUTS[ManagementEipAddress] = t.add_output(Output(
                    ManagementEipAddress,

                    Description="IP address of the management port on BIG-IP",
                    Value=Ref(ManagementEipAddress),

                ))

                if ha_type == "standalone":
                    OUTPUTS[VipPrivateIp] = t.add_output(Output(
                        VipPrivateIp,

                        Description="VIP on External Interface Secondary IP 1",
                        Value=Select("0", GetAtt(ExternalInterface, "SecondaryPrivateIpAddresses")),
                    ))

                    OUTPUTS[VipEipAddress] = t.add_output(Output(
                        VipEipAddress,

                        Description="EIP address for VIP",
                        Value=Join("", ["http://", Ref(VipEipAddress), ":80"]),
                    ))
                else:
                    # if clustered, needs to be cluster seed
                    if (BIGIP_INDEX + 1) == CLUSTER_SEED:
                        OUTPUTS[VipPrivateIp] = t.add_output(Output(
                            VipPrivateIp,

                            Description="VIP on External Interface Secondary IP 1",
                            Value=Select("0", GetAtt(ExternalInterface, "SecondaryPrivateIpAddresses")),
                        ))

                        OUTPUTS[VipEipAddress] = t.add_output(Output(
                            VipEipAddress,

                            Description="EIP address for VIP",
                            Value=Join("", ["http://", Ref(VipEipAddress), ":80"]),
                        ))

            if num_nics > 2:

                InternalInterface = "Bigip" + str(BIGIP_INDEX + 1) + "InternalInterface"
                InternalInterfacePrivateIp = "Bigip" + str(BIGIP_INDEX + 1) + "InternalInterfacePrivateIp"

                OUTPUTS[InternalInterface] = t.add_output(Output(
                    InternalInterface,

                    Description="Internal interface ID on BIG-IP",
                    Value=Ref(InternalInterface),

                ))

                OUTPUTS[InternalInterfacePrivateIp] = t.add_output(Output(
                    InternalInterfacePrivateIp,

                    Description="Internally routable IP of internal interface on BIG-IP",
                    Value=GetAtt(InternalInterface, "PrimaryPrivateIpAddress"),
                ))

    if webserver == True:
        webserverPrivateIp = t.add_output(Output(
            "webserverPrivateIp",
            Description="Private IP for Webserver",
            Value=GetAtt(Webserver, "PrivateIp"),
        ))

        WebserverPublicIp = t.add_output(Output(
            "WebserverPublicIp",
            Description="Public IP for Webserver",
            Value=GetAtt(Webserver, "PublicIp"),
        ))

        WebserverPublicUrl = t.add_output(Output(
            "WebserverPublicUrl",
            Description="Public URL for the Webserver",
            Value=Join("", ["http://", GetAtt(Webserver, "PublicIp")]),
        ))


    if stack == "full":
        print(t.to_json(indent=4))
    else:
        print(t.to_json(indent=4))  

if __name__ == "__main__":
    main()