```
AWSTemplateFormatVersion: '2010-09-09'

Description: 'Secure VPC Infrastructure for Taipei Region - Fixed Circular Dependency'

  

Parameters:

  ProjectName:

    Type: String

    Default: 'seoul-moment'

    Description: 'Project name prefix for all resources'

  

Resources:

  # ========== VPC & NETWORKING ==========

  VPC:

    Type: AWS::EC2::VPC

    Properties:

      CidrBlock: '10.1.0.0/16'

      EnableDnsHostnames: true

      EnableDnsSupport: true

      Tags:

        - Key: Name

          Value: !Sub '${ProjectName}-vpc'

  

  InternetGateway:

    Type: AWS::EC2::InternetGateway

    Properties:

      Tags:

        - Key: Name

          Value: !Sub '${ProjectName}-igw'

  

  InternetGatewayAttachment:

    Type: AWS::EC2::VPCGatewayAttachment

    Properties:

      InternetGatewayId: !Ref InternetGateway

      VpcId: !Ref VPC

  

  # Subnets

  PublicSubnet1:

    Type: AWS::EC2::Subnet

    Properties:

      VpcId: !Ref VPC

      AvailabilityZone: !Select [0, !GetAZs '']

      CidrBlock: '10.1.0.0/20'

      Tags:

        - Key: Name

          Value: !Sub '${ProjectName}-pub-1a'

  

  PublicSubnet2:

    Type: AWS::EC2::Subnet

    Properties:

      VpcId: !Ref VPC

      AvailabilityZone: !Select [1, !GetAZs '']

      CidrBlock: '10.1.16.0/20'

      Tags:

        - Key: Name

          Value: !Sub '${ProjectName}-pub-1b'

  

  PrivateSubnet1:

    Type: AWS::EC2::Subnet

    Properties:

      VpcId: !Ref VPC

      AvailabilityZone: !Select [0, !GetAZs '']

      CidrBlock: '10.1.128.0/20'

      Tags:

        - Key: Name

          Value: !Sub '${ProjectName}-pri-1a'

  

  PrivateSubnet2:

    Type: AWS::EC2::Subnet

    Properties:

      VpcId: !Ref VPC

      AvailabilityZone: !Select [1, !GetAZs '']

      CidrBlock: '10.1.144.0/20'

      Tags:

        - Key: Name

          Value: !Sub '${ProjectName}-pri-1b'

  

  # Routing

  PublicRouteTable:

    Type: AWS::EC2::RouteTable

    Properties:

      VpcId: !Ref VPC

      Tags:

        - Key: Name

          Value: !Sub '${ProjectName}-rtb-public'

  

  PublicRoute:

    Type: AWS::EC2::Route

    DependsOn: InternetGatewayAttachment

    Properties:

      RouteTableId: !Ref PublicRouteTable

      DestinationCidrBlock: '0.0.0.0/0'

      GatewayId: !Ref InternetGateway

  

  PublicSubnet1Assoc:

    Type: AWS::EC2::SubnetRouteTableAssociation

    Properties:

      RouteTableId: !Ref PublicRouteTable

      SubnetId: !Ref PublicSubnet1

  

  PublicSubnet2Assoc:

    Type: AWS::EC2::SubnetRouteTableAssociation

    Properties:

      RouteTableId: !Ref PublicRouteTable

      SubnetId: !Ref PublicSubnet2

  

  # ========== SECURITY GROUPS (SHELLS ONLY) ==========

  

  DefaultSecurityGroup:

    Type: AWS::EC2::SecurityGroup

    Properties:

      GroupDescription: 'Default restricted SG'

      VpcId: !Ref VPC

      Tags: [{Key: Name, Value: 'default-restricted'}]

  

  ALBSecurityGroup:

    Type: AWS::EC2::SecurityGroup

    Properties:

      GroupDescription: 'SG for ALB'

      VpcId: !Ref VPC

      Tags: [{Key: Name, Value: 'SG-ALB'}]

  

  WebServerSecurityGroup:

    Type: AWS::EC2::SecurityGroup

    Properties:

      GroupDescription: 'SG for Web Servers'

      VpcId: !Ref VPC

      Tags: [{Key: Name, Value: 'SG-WEB-SERVER'}]

  

  ECSSecurityGroup:

    Type: AWS::EC2::SecurityGroup

    Properties:

      GroupDescription: 'SG for ECS Tasks'

      VpcId: !Ref VPC

      Tags: [{Key: Name, Value: 'SG-ECS'}]

  

  DatabaseSecurityGroup:

    Type: AWS::EC2::SecurityGroup

    Properties:

      GroupDescription: 'SG for RDS'

      VpcId: !Ref VPC

      Tags: [{Key: Name, Value: 'SG-DATABASE'}]

  

  CacheSecurityGroup:

    Type: AWS::EC2::SecurityGroup

    Properties:

      GroupDescription: 'SG for Redis'

      VpcId: !Ref VPC

      Tags: [{Key: Name, Value: 'SG-CACHE'}]

  

  BastionSecurityGroup:

    Type: AWS::EC2::SecurityGroup

    Properties:

      GroupDescription: 'SG for Bastion Host'

      VpcId: !Ref VPC

      Tags: [{Key: Name, Value: 'SG-BASTION'}]

  

  ECSTemplateSecurityGroup:

    Type: AWS::EC2::SecurityGroup

    Properties:

      GroupDescription: 'SG for ECS Templates'

      VpcId: !Ref VPC

      Tags: [{Key: Name, Value: 'ecs-template-sg'}]

  

  # ========== SECURITY GROUP RULES (DETACHED) ==========

  

  # 1. Default SG Rules

  DefaultIngress:

    Type: AWS::EC2::SecurityGroupIngress

    Properties:

      GroupId: !Ref DefaultSecurityGroup

      IpProtocol: -1

      SourceSecurityGroupId: !Ref DefaultSecurityGroup

  

  # 2. ALB Rules

  ALBIngressHTTP:

    Type: AWS::EC2::SecurityGroupIngress

    Properties:

      GroupId: !Ref ALBSecurityGroup

      IpProtocol: tcp

      FromPort: 80

      ToPort: 80

      CidrIp: 0.0.0.0/0

  ALBIngressHTTPS:

    Type: AWS::EC2::SecurityGroupIngress

    Properties:

      GroupId: !Ref ALBSecurityGroup

      IpProtocol: tcp

      FromPort: 443

      ToPort: 443

      CidrIp: 0.0.0.0/0

  

  ALBEgressToWeb:

    Type: AWS::EC2::SecurityGroupEgress

    Properties:

      GroupId: !Ref ALBSecurityGroup

      IpProtocol: tcp

      FromPort: 3000

      ToPort: 3000

      DestinationSecurityGroupId: !Ref WebServerSecurityGroup

  

  # 3. Web Server Rules

  WebIngressFromALB:

    Type: AWS::EC2::SecurityGroupIngress

    Properties:

      GroupId: !Ref WebServerSecurityGroup

      IpProtocol: tcp

      FromPort: 3000

      ToPort: 3000

      SourceSecurityGroupId: !Ref ALBSecurityGroup

  

  WebIngressFromBastion:

    Type: AWS::EC2::SecurityGroupIngress

    Properties:

      GroupId: !Ref WebServerSecurityGroup

      IpProtocol: tcp

      FromPort: 22

      ToPort: 22

      SourceSecurityGroupId: !Ref BastionSecurityGroup

  

  WebEgressToDB:

    Type: AWS::EC2::SecurityGroupEgress

    Properties:

      GroupId: !Ref WebServerSecurityGroup

      IpProtocol: tcp

      FromPort: 5432

      ToPort: 5432

      DestinationSecurityGroupId: !Ref DatabaseSecurityGroup

  

  WebEgressToCache:

    Type: AWS::EC2::SecurityGroupEgress

    Properties:

      GroupId: !Ref WebServerSecurityGroup

      IpProtocol: tcp

      FromPort: 6379

      ToPort: 6379

      DestinationSecurityGroupId: !Ref CacheSecurityGroup

  

  WebEgressInternet:

    Type: AWS::EC2::SecurityGroupEgress

    Properties:

      GroupId: !Ref WebServerSecurityGroup

      IpProtocol: tcp

      FromPort: 80

      ToPort: 443

      CidrIp: 0.0.0.0/0

  

  # 4. ECS Rules (Similar to Web)

  ECSIngressFromALB:

    Type: AWS::EC2::SecurityGroupIngress

    Properties:

      GroupId: !Ref ECSSecurityGroup

      IpProtocol: tcp

      FromPort: 3000

      ToPort: 3000

      SourceSecurityGroupId: !Ref ALBSecurityGroup

  

  ECSIngressFromBastion:

    Type: AWS::EC2::SecurityGroupIngress

    Properties:

      GroupId: !Ref ECSSecurityGroup

      IpProtocol: tcp

      FromPort: 22

      ToPort: 22

      SourceSecurityGroupId: !Ref BastionSecurityGroup

  

  # 5. Database Rules

  DBIngressFromWeb:

    Type: AWS::EC2::SecurityGroupIngress

    Properties:

      GroupId: !Ref DatabaseSecurityGroup

      IpProtocol: tcp

      FromPort: 5432

      ToPort: 5432

      SourceSecurityGroupId: !Ref WebServerSecurityGroup

  

  DBIngressFromECS:

    Type: AWS::EC2::SecurityGroupIngress

    Properties:

      GroupId: !Ref DatabaseSecurityGroup

      IpProtocol: tcp

      FromPort: 5432

      ToPort: 5432

      SourceSecurityGroupId: !Ref ECSSecurityGroup

  

  DBIngressFromBastion:

    Type: AWS::EC2::SecurityGroupIngress

    Properties:

      GroupId: !Ref DatabaseSecurityGroup

      IpProtocol: tcp

      FromPort: 5432

      ToPort: 5432

      SourceSecurityGroupId: !Ref BastionSecurityGroup

  

  # 6. Cache Rules

  CacheIngressFromWeb:

    Type: AWS::EC2::SecurityGroupIngress

    Properties:

      GroupId: !Ref CacheSecurityGroup

      IpProtocol: tcp

      FromPort: 6379

      ToPort: 6379

      SourceSecurityGroupId: !Ref WebServerSecurityGroup

  

  CacheIngressFromECS:

    Type: AWS::EC2::SecurityGroupIngress

    Properties:

      GroupId: !Ref CacheSecurityGroup

      IpProtocol: tcp

      FromPort: 6379

      ToPort: 6379

      SourceSecurityGroupId: !Ref ECSSecurityGroup

  

  CacheIngressFromBastion:

    Type: AWS::EC2::SecurityGroupIngress

    Properties:

      GroupId: !Ref CacheSecurityGroup

      IpProtocol: tcp

      FromPort: 6379

      ToPort: 6379

      SourceSecurityGroupId: !Ref BastionSecurityGroup

  

  # 7. Bastion Rules

  BastionIngressSSH:

    Type: AWS::EC2::SecurityGroupIngress

    Properties:

      GroupId: !Ref BastionSecurityGroup

      IpProtocol: tcp

      FromPort: 22

      ToPort: 22

      CidrIp: 0.0.0.0/0 # 실제 환경에서는 본인 IP로 제한 권장

  

  BastionEgressToWeb:

    Type: AWS::EC2::SecurityGroupEgress

    Properties:

      GroupId: !Ref BastionSecurityGroup

      IpProtocol: tcp

      FromPort: 22

      ToPort: 22

      DestinationSecurityGroupId: !Ref WebServerSecurityGroup

  

  BastionEgressToDB:

    Type: AWS::EC2::SecurityGroupEgress

    Properties:

      GroupId: !Ref BastionSecurityGroup

      IpProtocol: tcp

      FromPort: 5432

      ToPort: 5432

      DestinationSecurityGroupId: !Ref DatabaseSecurityGroup

  

  BastionEgressToCache:

    Type: AWS::EC2::SecurityGroupEgress

    Properties:

      GroupId: !Ref BastionSecurityGroup

      IpProtocol: tcp

      FromPort: 6379

      ToPort: 6379

      DestinationSecurityGroupId: !Ref CacheSecurityGroup

  

  BastionEgressInternet:

    Type: AWS::EC2::SecurityGroupEgress

    Properties:

      GroupId: !Ref BastionSecurityGroup

      IpProtocol: tcp

      FromPort: 443

      ToPort: 443

      CidrIp: 0.0.0.0/0

  

  # 8. ECS Template Rules

  ECSTemplateIngressHTTP:

    Type: AWS::EC2::SecurityGroupIngress

    Properties:

      GroupId: !Ref ECSTemplateSecurityGroup

      IpProtocol: tcp

      FromPort: 80

      ToPort: 80

      SourceSecurityGroupId: !Ref ALBSecurityGroup

  

  ECSTemplateEgressAll:

    Type: AWS::EC2::SecurityGroupEgress

    Properties:

      GroupId: !Ref ECSTemplateSecurityGroup

      IpProtocol: -1

      CidrIp: 0.0.0.0/0

  

Outputs:

  VPCId:

    Value: !Ref VPC

    Export: { Name: !Sub '${ProjectName}-VPC-ID' }

  ALBSGID:

    Value: !Ref ALBSecurityGroup

    Export: { Name: !Sub '${ProjectName}-ALBSG-ID' }

  WebServerSGID:

    Value: !Ref WebServerSecurityGroup

    Export: { Name: !Sub '${ProjectName}-WebServerSG-ID' }

  # (이하 필요한 Output 추가 가능)
```