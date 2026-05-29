# CLAUDE.md — 프로젝트 작업 규칙

> NICECHAT_BASE 작업 시 따르는 규칙. 코드/아키텍처 설명은 `README.md` 참고.

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.


## Git 커밋 & 원격(remote) 컨벤션

### 1) 브랜치 전략
- `main` — 항상 초록불(green) 상태. **직접 푸시 금지**, PR 로만 병합.
- 작업 브랜치는 `main` 에서 분기하고, 끝나면 PR → `main`.
- 브랜치 네이밍: `<type>/phase<N>-<짧은-설명>`
  - 예) `feat/phase1-sync-chat`, `fix/phase3-qdrant-conn`, `chore/phase0-ci`
  - Phase 와 무관한 작업은 `<type>/<짧은-설명>` (예: `docs/readme-roadmap`).

### 2) 커밋 메시지 — Conventional Commits
형식: `<type>(<scope>): <subject>`

- **type**: `feat` | `fix` | `docs` | `refactor` | `test` | `chore` | `perf` | `ci` | `build`
- **scope**(선택): 변경 영역. 디렉터리/계층 기준 권장 — `ir/vector`, `workflow`, `clients`, `core`, `api`, `workers`, `middleware`.
  - Phase 단위 작업이면 `phase3` 처럼 phase 를 scope 로 써도 됨.
- **subject**: 명령형 현재시제, 소문자 시작, 마침표 없음, 한 줄 50자 내외.
  - 한글 본문도 허용하되 `type/scope` 키워드는 영어로 통일.

본문(선택)은 빈 줄 뒤에 *무엇을/왜* 를 적는다(어떻게는 코드가 말함). 이슈 연결은 푸터에 `Refs #12` / `Closes #12`.

예시:
```
feat(ir/vector): add dense+BM25 RRF fusion in search

dense 단독 대비 한국어 질의 recall 향상. tokenize_ko 형태소
분리 후 BM25 점수와 RRF 로 융합.

Refs #14
```

### 3) 커밋 단위
- **한 커밋 = 한 논리적 변경.** Phase 검증(서버 부팅 + `pytest` 통과)을 깨지 않는 단위로 쪼갠다.
- 커밋 전 로컬 검증: `make lint` · `make type` · `make test` (pre-commit 의 ruff 가 자동 정리).
- `uv.lock` 변경은 의존성 변경 커밋에 **함께** 포함한다 (`chore(deps): ...`).

### 4) 원격 푸시 / PR
- `git push -u origin <branch>` 로 작업 브랜치를 올리고 PR 을 연다. `main` 직접 푸시·force push 금지.
- CI(`.github/workflows/ci.yml`)가 ruff/mypy/pytest 를 돌린다. **CI 초록불 + 리뷰 통과** 후 병합.
- 병합은 squash 권장 (PR 제목을 Conventional Commits 형식으로 → 히스토리 정리).
- 사용자가 명시적으로 요청할 때만 커밋·푸시한다.

### 5) 에이전트 커밋 트레일러
Claude/에이전트가 만든 커밋은 메시지 끝에 공동저자 트레일러를 붙인다:
```
Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
```
