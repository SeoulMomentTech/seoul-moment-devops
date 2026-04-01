# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

"Seoul Moment" (서울 모먼트) AWS infrastructure defined as CloudFormation templates. The project provisions a production VPC with a multi-tier security architecture optimized for cost (Single-AZ, Graviton/t4g instances, minimal retention).

## Stack Deployment Order

The templates use cross-stack references via `!ImportValue` and **must be deployed in this order**:

1. **`CloudFormation_VPC_SG.yml`** — VPC, subnets, routing, and all security groups (shell definitions + detached ingress/egress rules to avoid circular dependencies). Exports VPC ID, subnet IDs, and all SG IDs.
2. **`CloudFormation_ECR_RDS.yml`** — ECR repository (`seoul-moment-api`), Secrets Manager for DB credentials, RDS PostgreSQL 13 (Single-AZ, `db.t4g.micro`), CloudWatch log group, enhanced monitoring IAM role. Imports private subnets and DatabaseSG.
3. **`CloudFormation_CACHE.yml`** — ElastiCache Redis 7.1 replication group (`cache.t4g.micro`), parameter group, CloudWatch alarms (CPU, memory, connections). Imports private subnets and CacheSG.
4. **`CloudFormation_Bastion.yml`** — Bastion EC2 instance (`t4g.nano`, AL2023 ARM64) in public subnet. Imports PublicSubnet1 and BastionSG.

## Key Conventions

- All resources share the `ProjectName` parameter (default: `seoul-moment`). This must be identical across all stacks for cross-stack imports to resolve.
- Security groups are created as empty shells first, then rules are added as separate `AWS::EC2::SecurityGroupIngress/Egress` resources — this pattern avoids circular dependency issues.
- Cost optimization choices: Single-AZ RDS, no Multi-AZ Redis, Graviton (ARM) instance types, short log retention (3 days), ECR lifecycle keeping only 5 images.
- RDS has `DeletionPolicy: Retain` and `DeletionProtection: true`.

## Validation

```bash
aws cloudformation validate-template --template-body file://CloudFormation_VPC_SG.yml
aws cloudformation validate-template --template-body file://CloudFormation_ECR_RDS.yml
aws cloudformation validate-template --template-body file://CloudFormation_CACHE.yml
aws cloudformation validate-template --template-body file://CloudFormation_Bastion.yml
```

## Network Layout

- VPC CIDR: `10.1.0.0/16`
- Public subnets: `10.1.0.0/20` (AZ-a), `10.1.16.0/20` (AZ-b)
- Private subnets: `10.1.128.0/20` (AZ-a), `10.1.144.0/20` (AZ-b)
- App port: 3000 (Web/ECS), DB: PostgreSQL 5432, Cache: Redis 6379, Bastion: SSH 22
