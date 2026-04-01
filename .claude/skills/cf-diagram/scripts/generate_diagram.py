#!/usr/bin/env python3
"""
CloudFormation 템플릿을 파싱하여 Mermaid.js 기반 아키텍처 다이어그램 HTML을 생성한다.

사용법:
    python generate_diagram.py --dir <CF 템플릿 디렉토리> --output <출력파일.html>
"""

import argparse
import glob
import os
import sys
import re

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML이 필요합니다. 'pip install pyyaml' 로 설치하세요.", file=sys.stderr)
    sys.exit(1)


# ── CloudFormation 인트린식 함수 YAML 핸들러 ──

class CFTag:
    """CloudFormation 인트린식 함수 값을 보존하는 래퍼."""
    def __init__(self, tag, value):
        self.tag = tag
        self.value = value
    def __repr__(self):
        return f"CFTag({self.tag}, {self.value})"


def _cf_constructor(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return CFTag(tag_suffix, loader.construct_scalar(node))
    elif isinstance(node, yaml.SequenceNode):
        return CFTag(tag_suffix, loader.construct_sequence(node))
    elif isinstance(node, yaml.MappingNode):
        return CFTag(tag_suffix, loader.construct_mapping(node))
    return CFTag(tag_suffix, None)


class CFLoader(yaml.SafeLoader):
    pass

# !Ref, !Sub, !GetAtt, !Select, !Join, !ImportValue, !If, !Equals, !Not, !GetAZs, !Split, !Condition
for fn in ['Ref', 'Sub', 'GetAtt', 'Select', 'Join', 'ImportValue', 'If',
           'Equals', 'Not', 'GetAZs', 'Split', 'Condition', 'FindInMap',
           'Base64', 'Cidr', 'Transform']:
    CFLoader.add_multi_constructor(f'!{fn}', lambda loader, suffix, node, t=fn: _cf_constructor(loader, t, node))
# short-form tags without suffix
for fn in ['Ref', 'Sub', 'GetAtt', 'Select', 'Join', 'ImportValue', 'If',
           'Equals', 'Not', 'GetAZs', 'Split', 'Condition', 'FindInMap',
           'Base64', 'Cidr', 'Transform']:
    try:
        CFLoader.add_constructor(f'!{fn}', lambda loader, node, t=fn: _cf_constructor(loader, t, node))
    except Exception:
        pass


# ── 파싱 ──

def load_templates(directory):
    """디렉토리에서 모든 CloudFormation YAML 파일을 로드한다."""
    templates = {}
    patterns = [os.path.join(directory, '*.yml'), os.path.join(directory, '*.yaml')]
    for pat in patterns:
        for fpath in glob.glob(pat):
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    doc = yaml.load(f, Loader=CFLoader)
                if doc and isinstance(doc, dict) and 'AWSTemplateFormatVersion' in doc:
                    templates[os.path.basename(fpath)] = doc
            except Exception as e:
                print(f"WARNING: {fpath} 파싱 실패: {e}", file=sys.stderr)
    return templates


def resolve_ref(value):
    """!Ref 등의 참조에서 논리적 ID를 추출한다."""
    if isinstance(value, CFTag):
        if value.tag == 'Ref':
            return value.value
        return str(value.value)
    if isinstance(value, dict):
        if 'Ref' in value:
            return value['Ref']
        if 'Fn::GetAtt' in value:
            v = value['Fn::GetAtt']
            return v[0] if isinstance(v, list) else v.split('.')[0]
    if isinstance(value, str):
        return value
    return ''


def get_tag_value(tags, key='Name'):
    """Tags 리스트에서 특정 키의 값을 추출한다."""
    if not isinstance(tags, list):
        return ''
    for tag in tags:
        if isinstance(tag, dict) and tag.get('Key') == key:
            val = tag.get('Value', '')
            if isinstance(val, CFTag):
                return str(val.value)
            return str(val)
    return ''


def extract_architecture(templates):
    """모든 템플릿에서 아키텍처 구성 요소를 추출한다."""
    vpc_info = {}
    subnets = []
    security_groups = []
    sg_rules = []
    other_resources = []

    sg_logical_ids = set()

    for filename, template in templates.items():
        resources = template.get('Resources', {})
        if not isinstance(resources, dict):
            continue

        for logical_id, res in resources.items():
            if not isinstance(res, dict):
                continue
            res_type = res.get('Type', '')
            props = res.get('Properties', {}) or {}

            # VPC
            if res_type == 'AWS::EC2::VPC':
                cidr = props.get('CidrBlock', '')
                if isinstance(cidr, CFTag):
                    cidr = str(cidr.value)
                vpc_info = {'logical_id': logical_id, 'cidr': cidr}

            # Subnets
            elif res_type == 'AWS::EC2::Subnet':
                cidr = props.get('CidrBlock', '')
                if isinstance(cidr, CFTag):
                    cidr = str(cidr.value)
                name = get_tag_value(props.get('Tags', []))
                subnets.append({
                    'logical_id': logical_id,
                    'cidr': cidr,
                    'display_name': name or logical_id,
                    'is_public': 'pub' in name.lower() or 'public' in logical_id.lower()
                })

            # Security Groups
            elif res_type == 'AWS::EC2::SecurityGroup':
                display = get_tag_value(props.get('Tags', []))
                sg_logical_ids.add(logical_id)
                security_groups.append({
                    'logical_id': logical_id,
                    'display_name': display or logical_id,
                    'description': props.get('GroupDescription', '')
                })

            # SG Ingress Rules
            elif res_type == 'AWS::EC2::SecurityGroupIngress':
                group_id = resolve_ref(props.get('GroupId', ''))
                source_sg = resolve_ref(props.get('SourceSecurityGroupId', ''))
                cidr = props.get('CidrIp', '')
                if isinstance(cidr, CFTag):
                    cidr = str(cidr.value)
                from_port = props.get('FromPort', '')
                to_port = props.get('ToPort', '')
                protocol = props.get('IpProtocol', 'tcp')
                sg_rules.append({
                    'type': 'ingress',
                    'name': logical_id,
                    'group_id': group_id,
                    'source_sg': source_sg,
                    'cidr': cidr,
                    'from_port': from_port,
                    'to_port': to_port,
                    'protocol': protocol
                })

            # SG Egress Rules
            elif res_type == 'AWS::EC2::SecurityGroupEgress':
                group_id = resolve_ref(props.get('GroupId', ''))
                dest_sg = resolve_ref(props.get('DestinationSecurityGroupId', ''))
                cidr = props.get('CidrIp', '')
                if isinstance(cidr, CFTag):
                    cidr = str(cidr.value)
                from_port = props.get('FromPort', '')
                to_port = props.get('ToPort', '')
                protocol = props.get('IpProtocol', 'tcp')
                sg_rules.append({
                    'type': 'egress',
                    'name': logical_id,
                    'group_id': group_id,
                    'dest_sg': dest_sg,
                    'cidr': cidr,
                    'from_port': from_port,
                    'to_port': to_port,
                    'protocol': protocol
                })

            # Other notable resources
            elif res_type in (
                'AWS::RDS::DBInstance', 'AWS::ElastiCache::ReplicationGroup',
                'AWS::ECS::Cluster', 'AWS::ECS::Service',
                'AWS::ElasticLoadBalancingV2::LoadBalancer',
                'AWS::EC2::Instance', 'AWS::ECR::Repository',
                'AWS::ECS::TaskDefinition'
            ):
                other_resources.append({
                    'logical_id': logical_id,
                    'type': res_type,
                    'filename': filename
                })

    return vpc_info, subnets, security_groups, sg_rules, other_resources


# ── Mermaid 다이어그램 생성 ──

SG_COLORS = {
    'ALB': '#FF9900',
    'Bastion': '#3F1D7B',
    'Web': '#FF9900',
    'ECS': '#FF9900',
    'Database': '#2E7D32',
    'Cache': '#C62828',
    'Default': '#607D8B',
    'ECSTemplate': '#795548',
}


def get_sg_color(logical_id):
    for key, color in SG_COLORS.items():
        if key.lower() in logical_id.lower():
            return color
    return SG_COLORS['Default']


def generate_mermaid(vpc_info, subnets, sgs, rules):
    """SG 간 트래픽 흐름을 Mermaid flowchart로 생성한다."""
    lines = ['flowchart LR']

    # Internet 노드
    lines.append('    Internet(("☁️ Internet"))')
    lines.append('')

    # VPC subgraph
    vpc_label = f"VPC ({vpc_info.get('cidr', '')})" if vpc_info else "VPC"
    lines.append(f'    subgraph VPC["{vpc_label}"]')
    lines.append('        direction LR')

    # SG 노드
    for sg in sgs:
        if 'default' in sg['logical_id'].lower() and 'restricted' in sg.get('description', '').lower():
            continue
        display = sg['display_name']
        lines.append(f'        {sg["logical_id"]}["{display}"]')

    lines.append('    end')
    lines.append('')

    # 인터넷 → SG (인그레스 0.0.0.0/0)
    seen_edges = set()
    for rule in rules:
        if rule['type'] == 'ingress' and rule.get('cidr') == '0.0.0.0/0':
            target = rule['group_id']
            to_port = rule.get('to_port', '')
            from_port = rule.get('from_port', '')
            proto = str(rule.get('protocol', 'tcp')).upper()
            if proto == '-1':
                label = 'ALL'
            elif from_port and to_port and str(from_port) != str(to_port):
                label = f"{proto}/{from_port}-{to_port}"
            else:
                label = f"{proto}/{to_port}"

            # 같은 SG 대상의 HTTP/HTTPS를 합치기
            edge_key = f"Internet->{target}"
            if edge_key in seen_edges:
                continue

            # 같은 SG로 가는 모든 인터넷 인그레스 규칙 수집
            same_target_rules = [r for r in rules
                                 if r['type'] == 'ingress'
                                 and r.get('cidr') == '0.0.0.0/0'
                                 and r['group_id'] == target]
            if len(same_target_rules) > 1:
                labels = []
                for r in same_target_rules:
                    p = str(r.get('protocol', 'tcp')).upper()
                    tp = r.get('to_port', '')
                    fp = r.get('from_port', '')
                    if p == '-1':
                        labels.append('ALL')
                    elif fp and tp and str(fp) != str(tp):
                        labels.append(f"{p}/{fp}-{tp}")
                    else:
                        labels.append(f"{p}/{tp}")
                label = ', '.join(labels)

            seen_edges.add(edge_key)
            lines.append(f'    Internet -->|"{label}"| {target}')

    lines.append('')

    # SG → SG (인그레스 규칙 기반)
    for rule in rules:
        if rule['type'] == 'ingress' and rule.get('source_sg'):
            src = rule['source_sg']
            dst = rule['group_id']
            port = rule.get('to_port', '')
            proto = str(rule.get('protocol', 'tcp')).upper()
            if proto == '-1':
                label = 'ALL'
            else:
                label = f"TCP/{port}"
            edge_key = f"{src}->{dst}:{label}"
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                lines.append(f'    {src} -->|"{label}"| {dst}')

    return '\n'.join(lines)


def generate_subnet_section(subnets):
    """서브넷 정보를 HTML 테이블로 생성한다."""
    if not subnets:
        return ''

    public = [s for s in subnets if s['is_public']]
    private = [s for s in subnets if not s['is_public']]

    rows = ''
    for s in public:
        rows += f'<tr><td>🌐 {s["display_name"]}</td><td>{s["cidr"]}</td><td>Public</td></tr>\n'
    for s in private:
        rows += f'<tr><td>🔒 {s["display_name"]}</td><td>{s["cidr"]}</td><td>Private</td></tr>\n'

    return f"""
    <h2>Subnets</h2>
    <table>
        <thead><tr><th>Name</th><th>CIDR</th><th>Type</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>
    """


def generate_resource_section(resources):
    """기타 리소스를 HTML 테이블로 생성한다."""
    if not resources:
        return ''

    type_labels = {
        'AWS::RDS::DBInstance': 'RDS (PostgreSQL)',
        'AWS::ElastiCache::ReplicationGroup': 'ElastiCache (Redis)',
        'AWS::ECS::Cluster': 'ECS Cluster',
        'AWS::ECS::Service': 'ECS Service',
        'AWS::ElasticLoadBalancingV2::LoadBalancer': 'ALB',
        'AWS::EC2::Instance': 'EC2 Instance',
        'AWS::ECR::Repository': 'ECR Repository',
        'AWS::ECS::TaskDefinition': 'ECS Task Definition',
    }

    rows = ''
    for r in resources:
        label = type_labels.get(r['type'], r['type'])
        rows += f'<tr><td>{r["logical_id"]}</td><td>{label}</td><td>{r["filename"]}</td></tr>\n'

    return f"""
    <h2>Resources</h2>
    <table>
        <thead><tr><th>Logical ID</th><th>Type</th><th>Template</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>
    """


def generate_html(mermaid_code, vpc_info, subnets, sgs, rules, resources, output_path):
    """최종 HTML 파일을 생성한다."""

    # SG 스타일 생성
    style_lines = []
    for sg in sgs:
        if 'default' in sg['logical_id'].lower():
            continue
        color = get_sg_color(sg['logical_id'])
        style_lines.append(f'    style {sg["logical_id"]} fill:{color},stroke:#333,color:#fff')

    styled_mermaid = mermaid_code + '\n' + '\n'.join(style_lines)
    # Internet 노드 스타일
    styled_mermaid += '\n    style Internet fill:#4A90D9,stroke:#333,color:#fff'

    subnet_html = generate_subnet_section(subnets)
    resource_html = generate_resource_section(resources)

    # 규칙 요약
    sg_map = {sg['logical_id']: sg['display_name'] for sg in sgs}
    rule_rows = ''
    for rule in rules:
        if rule['type'] == 'ingress':
            src = sg_map.get(rule.get('source_sg', ''), rule.get('cidr', 'N/A'))
            dst = sg_map.get(rule['group_id'], rule['group_id'])
            port = rule.get('to_port', 'ALL')
            if not src:
                src = rule.get('cidr', 'N/A')
            rule_rows += f'<tr><td>{src}</td><td>{dst}</td><td>{port}</td><td>Ingress</td></tr>\n'

    rules_html = f"""
    <h2>Security Group Rules</h2>
    <table>
        <thead><tr><th>Source</th><th>Destination</th><th>Port</th><th>Direction</th></tr></thead>
        <tbody>{rule_rows}</tbody>
    </table>
    """ if rule_rows else ''

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CloudFormation Architecture Diagram</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f7fa; color: #333; padding: 2rem; }}
        h1 {{ text-align: center; margin-bottom: 0.5rem; color: #1a1a2e; }}
        .subtitle {{ text-align: center; color: #666; margin-bottom: 2rem; font-size: 0.9rem; }}
        .diagram-container {{ background: #fff; border-radius: 12px; padding: 2rem; box-shadow: 0 2px 12px rgba(0,0,0,0.08); margin-bottom: 2rem; overflow-x: auto; }}
        .mermaid {{ text-align: center; }}
        h2 {{ margin: 1.5rem 0 1rem; color: #1a1a2e; border-bottom: 2px solid #e0e0e0; padding-bottom: 0.5rem; }}
        table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 6px rgba(0,0,0,0.06); margin-bottom: 1.5rem; }}
        th {{ background: #2c3e50; color: #fff; padding: 0.75rem 1rem; text-align: left; font-weight: 500; }}
        td {{ padding: 0.6rem 1rem; border-bottom: 1px solid #eee; }}
        tr:hover td {{ background: #f8f9fa; }}
        .legend {{ display: flex; flex-wrap: wrap; gap: 1rem; margin: 1.5rem 0; }}
        .legend-item {{ display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; }}
        .legend-color {{ width: 16px; height: 16px; border-radius: 3px; }}
    </style>
</head>
<body>
    <h1>AWS Architecture Diagram</h1>
    <p class="subtitle">VPC {vpc_info.get('cidr', '')} &mdash; Auto-generated from CloudFormation templates</p>

    <div class="legend">
        <div class="legend-item"><div class="legend-color" style="background:#FF9900"></div> ALB / Web / ECS</div>
        <div class="legend-item"><div class="legend-color" style="background:#3F1D7B"></div> Bastion</div>
        <div class="legend-item"><div class="legend-color" style="background:#2E7D32"></div> Database</div>
        <div class="legend-item"><div class="legend-color" style="background:#C62828"></div> Cache</div>
        <div class="legend-item"><div class="legend-color" style="background:#4A90D9"></div> Internet</div>
    </div>

    <div class="diagram-container">
        <pre class="mermaid">
{styled_mermaid}
        </pre>
    </div>

    {subnet_html}
    {rules_html}
    {resource_html}

    <script>
        mermaid.initialize({{ startOnLoad: true, theme: 'default', flowchart: {{ useMaxWidth: true, htmlLabels: true, curve: 'basis' }} }});
    </script>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path


# ── Main ──

def main():
    parser = argparse.ArgumentParser(description='CloudFormation 템플릿에서 아키텍처 다이어그램 생성')
    parser.add_argument('--dir', default='.', help='CloudFormation 템플릿 디렉토리 (기본: 현재 디렉토리)')
    parser.add_argument('--output', default='cf-architecture-diagram.html', help='출력 HTML 파일 (기본: cf-architecture-diagram.html)')
    args = parser.parse_args()

    directory = os.path.abspath(args.dir)
    print(f"[DIR] {directory}")

    templates = load_templates(directory)
    if not templates:
        print("ERROR: CloudFormation templates not found.", file=sys.stderr)
        sys.exit(1)

    print(f"[TEMPLATES] {', '.join(templates.keys())}")

    vpc_info, subnets, sgs, rules, resources = extract_architecture(templates)

    print(f"[VPC] {vpc_info.get('cidr', 'N/A')}")
    print(f"[SUBNETS] {len(subnets)}")
    print(f"[SG] {len(sgs)}")
    print(f"[RULES] {len(rules)}")
    print(f"[RESOURCES] {len(resources)}")

    mermaid = generate_mermaid(vpc_info, subnets, sgs, rules)
    output = generate_html(mermaid, vpc_info, subnets, sgs, rules, resources, args.output)

    print(f"\n[DONE] {os.path.abspath(output)}")


if __name__ == '__main__':
    main()
