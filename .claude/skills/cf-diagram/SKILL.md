---
name: cf-diagram
description: "CloudFormation 템플릿을 분석하여 AWS 아키텍처 다이어그램(HTML)을 자동 생성하는 스킬. CloudFormation 아키텍처 다이어그램, 인프라 시각화, 네트워크 토폴로지 확인, SG 플로우 다이어그램 등을 요청할 때 사용한다. 사용자가 '다이어그램 만들어줘', '아키텍처 그려줘', '인프라 시각화', 'CF 템플릿 분석' 등의 표현을 쓸 때도 트리거한다."
---

# CF Diagram — CloudFormation 아키텍처 다이어그램 생성기

CloudFormation YAML 템플릿들을 파싱하여 VPC, 서브넷, 보안 그룹, 트래픽 흐름을 시각화하는 HTML 다이어그램을 생성한다.

## 동작 방식

1. 현재 디렉토리(또는 지정된 경로)에서 `*.yml` / `*.yaml` CloudFormation 템플릿을 모두 찾는다
2. 번들된 Python 스크립트(`scripts/generate_diagram.py`)를 실행하여 템플릿을 파싱한다
3. VPC, 서브넷, 보안 그룹, 인그레스/이그레스 규칙, 주요 리소스를 추출한다
4. Mermaid.js 기반 HTML 다이어그램 파일을 생성한다

## 사용법

아래 명령으로 다이어그램을 생성한다:

```bash
python "<이 스킬 경로>/scripts/generate_diagram.py" --dir "<CloudFormation 템플릿 디렉토리>" --output "<출력 HTML 파일 경로>"
```

- `--dir`: CloudFormation 템플릿이 있는 디렉토리 (기본값: 현재 디렉토리)
- `--output`: 출력 HTML 파일 경로 (기본값: `cf-architecture-diagram.html`)

생성된 HTML 파일을 브라우저에서 열면 아키텍처 다이어그램을 확인할 수 있다.

## 다이어그램에 포함되는 요소

| 요소 | 설명 |
|------|------|
| VPC | CIDR 블록과 함께 전체 경계 표시 |
| 서브넷 | Public/Private 구분, CIDR, AZ 표시 |
| 보안 그룹 | 색상으로 역할 구분 (ALB, Web, ECS, DB, Cache, Bastion) |
| 트래픽 흐름 | 인그레스 규칙 기반 화살표 + 포트/프로토콜 라벨 |
| 인터넷 | 0.0.0.0/0 소스의 인바운드 트래픽 표시 |

## 주의사항

- 이미 생성된 다이어그램이 있다면 다시 생성할 필요 없다. 템플릿이 변경되었을 때만 재생성한다.
- PyYAML이 설치되어 있어야 한다 (`pip install pyyaml`).
- CloudFormation 인트린식 함수(!Ref, !Sub, !ImportValue 등)를 처리한다.
