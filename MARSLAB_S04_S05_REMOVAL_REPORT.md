# MarsLab S04·S05 전량 제거 보고서

## 1. 제거 요청과 기준점

- 제거 대상: 기존 refactor plan의 `S04 - real Scene USDZ/Rover bundle validator`와
  `S05 - immutable RunPlan`에서 추가·수정한 tracked 변경 전체
- 보존 대상: 승인 완료된 S01–S03, 사용자 소유 미커밋 파일, 기존 submodule gitlink
- S03 승인 기준 SHA: `2f76557e6962f1cadffeaa876c34d9d00a9b8a93`
- 제거 전 SHA: `cdfa38b9f1908a655d415b4366de50bfda58863a`
- 제거 커밋: `119e8978e78a7eaa77ad83750866840093165b7c`
- 제거 후 tracked tree: `6c445f42e71cd235c5fdaa408b84dd2e95300c13`
- S03 기준 tracked tree: `6c445f42e71cd235c5fdaa408b84dd2e95300c13`

제거 후 tracked tree hash가 S03 승인 기준과 정확히 같으므로, S04·S05의 제품 코드,
테스트, manifest, 누적 보고서 변경은 전부 역적용되었고 S01–S03 tracked 결과만 남았다.

## 2. S04로 식별한 변경

S04 경계는 `2f76557..689fab8`이다. 이 단계는 12개 경로에 `+1,368/-21`을
추가했으며 다음 커밋 5개로 구성됐다.

| SHA | 커밋 |
|---|---|
| `d7fa4a3` | `feat(validation): inspect scene and rover USD assets` |
| `4ce7e9c` | `docs(refactor): record cumulative S01 to S04 changes` |
| `424b25a` | `docs(refactor): correct S04 report references` |
| `f7c88bb` | `docs(refactor): align S04 report with final evidence` |
| `689fab8` | `docs(refactor): clarify S04 atomicity evidence` |

### S04에서 추가되어 이번에 삭제된 파일

- `assets/robots/rover/manifest.json`
- `marslab/validation/__init__.py`
- `marslab/validation/assets.py`
- `marslab/validation/lightweight.py`
- `marslab/validation/models.py`
- `marslab/validation/openusd.py`
- `marslab/validation/paths.py`
- `marslab/validation/rover_file.py`
- `marslab/validation/semantic.py`
- `tests/refactor/test_asset_validator_failures.py`

### S04에서 수정되어 S03 상태로 복원된 파일

- `marslab/runtime/precheck.py`

### S04 보고서 변경의 복원

- S04·S05 누적 보고서 `MARSLAB_S01_S05_CHANGE_REPORT.md`는 삭제했다.
- S03 기준 보고서 `MARSLAB_S01_S03_CHANGE_REPORT.md`를 정확히 복원했다.

## 3. S05로 식별한 변경

S05 경계는 `689fab8..cdfa38b`이다. 이 단계는 16개 경로에 `+1,102/-312`를
추가했으며 다음 커밋 3개로 구성됐다.

| SHA | 커밋 |
|---|---|
| `ddd2824` | `feat(runtime): resolve immutable run plans` |
| `1f89556` | `docs(refactor): record cumulative S01 to S05 changes` |
| `cdfa38b` | `docs(refactor): fix S05 report QA surface` |

### S05에서 추가되어 이번에 삭제된 파일

- `marslab/runtime/run_plan.py`
- `tests/refactor/test_run_plan.py`
- `tests/refactor/test_typed_runtime_consumers.py`

### S05에서 수정되어 S03 상태로 복원된 파일

- `marslab/main.py`
- `marslab/robots/drive_api_setup.py`
- `marslab/robots/rover.py`
- `marslab/ros2_bridge/rclpy_integration.py`
- `marslab/ros2_bridge/sensor_graph.py`
- `marslab/runtime/articulation_setup.py`
- `marslab/runtime/atmosphere_boot.py`
- `marslab/runtime/loop_context.py`
- `marslab/runtime/sensor_frames.py`
- `marslab/sensors/sensor_spawner.py`
- `tests/refactor/test_no_utils_dependencies.py`
- `tests/refactor/test_rover_schema.py`

## 4. 제거 규모

S04와 S05를 합치면 제거 전 기준으로 28개 tracked 경로에 `+2,748/-611`의
변경이 있었다. 역적용 커밋은 그 반대인 `+611/-2,748`이며, 추가 611줄은 새 기능이
아니라 S03 코드와 S03 누적 보고서를 원상 복원한 행이다.

| 결과 | 수량 |
|---|---:|
| S04·S05 전용 파일 삭제 | 14개(누적 S01–S05 보고서 포함) |
| S03 버전으로 복원된 코드·테스트 파일 | 13개 |
| S03 누적 보고서 복원 | 1개 |
| 최종 tracked tree 차이(S03 대비) | 0 |

## 5. 보존한 항목

다음은 S04·S05의 tracked 구현 변경이 아니므로 삭제하거나 수정하지 않았다.

- `.gitignore`의 사용자 수정
- `MARSLAB_STALE_RESIDUE_AUDIT.md`
- `MarsLab.pdf`
- `MarsLab_refactoring.md`
- `package-lock.json`
- `assets/m2020-urdf-models` submodule의 기존 gitlink

`.omo/evidence/marslab-reference-runtime-refactor/` 아래의 S04·S05 검증 기록은 제품
구현이 아니라 변경 이력과 승인 감사 자료이므로 삭제하지 않고 `invalidated` 상태로
보존했다. 이 기록은 앞으로 S04·S05 구현이 존재한다는 근거로 재사용할 수 없다.

submodule 작업 디렉터리가 초기화되어 있는지는 로컬 checkout 상태이며 S04·S05의
tracked diff가 아니다. 따라서 데이터 삭제를 피하기 위해 deinitialize하지 않았다.

## 6. 검증 결과

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH= python3 -m pytest tests/refactor -q
31 passed
```

- `git write-tree`와 S03 기준 tree hash 일치: PASS
- S04/S05 전용 `run_plan.py`, `marslab/validation/`, manifest 및 3개 테스트 파일 부재: PASS
- `RunPlan`, `ResolvedInputs`, `marslab.validation`, `build_run_plan`,
  `build_validate_plan` 잔존 참조 검사: PASS(검색 결과 없음)
- 변경·복원된 Python 13개 파일 Black 검사: PASS
- Ruff 검사: PASS
- `compileall`: PASS
- `git diff --check`: PASS
- 사용자 소유 5개 파일 SHA-256 제거 전후 동일: PASS

전체 `black --check marslab/ tests/`에는 이번 제거와 관계없는 기존 파일
`marslab/ros2_bridge/imu_noise_publisher.py`와
`marslab/ros2_bridge/wheel_odometry_publisher.py`의 포맷 차이가 남아 있다. 이번에
복원한 파일만 대상으로 한 Black 검사는 통과했으며, 이 두 파일은 수정하지 않았다.

## 7. 현재 상태

- S01–S03 구현과 `MARSLAB_S01_S03_CHANGE_REPORT.md`는 유지된다.
- S04 자산 정밀 validator와 Rover manifest는 MarsLab에서 제거됐다.
- S05 RunPlan/ResolvedInputs 및 typed runtime consumer 변경은 제거됐다.
- 기존 S04 승인과 S05 후보 증거는 ledger에서 무효화했으며 재사용할 수 없다.
- 이후 통합 YAML과 최소 runtime 실패 처리의 책임 경계는 새 계획에서 다시 결정한다.
