include ~/.claude/Makefile.common

.PHONY: help lint lint-render test new_project new_project_dev run_copier check_tools preview_defaults project

input_dir := .

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

lint:  ## Validate template paths, copier config, and Python lint
	@python3 tools/template/validate_paths.py
	@ruff check tools/template/

## Lint the SCAFFOLD by rendering it and running the rendered project's own
## `make lint-check`. `make lint` above only covers tools/template/ — it cannot touch
## template/_scaffold/, whose files carry Jinja in both paths and bodies and so
## are unparseable by ruff until rendered. Without this target the scaffold's
## Python is linted exclusively by test-render.yml's "Lint rendered project"
## step, i.e. only after push (PR #65 shipped RUF046 + 6 unformatted files
## green locally on exactly this gap).
##
## Two profiles, chosen for lint COVERAGE rather than feature breadth:
##   defaults  the baseline scaffold surface
##   ml        adds {{ ml_source_root }} to the render's LINT_PATHS; with
##             include_ml=false the ML tree is rm -rf'd at render time, so it
##             is entirely lint-invisible without this row (this is the profile
##             PR #65 broke)
## Mirrors the CI step's install: lint needs the dev group (ruff) only, not the
## ~2GB agent runtime, hence `uv sync --only-group dev` + UV_NO_SYNC=1 to stop
## `uv run` re-syncing the full project underneath it.
##
## copier narrates 50+ _tasks to stderr; that is captured per-profile and only
## replayed when a render fails, so a passing run shows just the lint results.
##
## Usage: make lint-render                    (both profiles, temp dirs removed)
##        make lint-render KEEP=1             (leave the renders in place)
##        make lint-render PROFILES=ml        (one profile)
##        make lint-render DST=/some/path     (render root you choose, kept)
lint-render: check_tools
	@set -u; \
	failed=""; \
	for profile in $${PROFILES:-defaults ml}; do \
	  case "$$profile" in \
	    defaults) extra="" ;; \
	    ml) extra="-d include_ml=true" ;; \
	    *) echo "unknown profile: $$profile (valid: defaults ml)"; exit 2 ;; \
	  esac; \
	  if [ -n "$${DST:-}" ]; then dst="$$DST/$$profile"; keep=1; mkdir -p "$$dst"; \
	  else dst="$$(mktemp -d -t ait_lint_$$profile)"; keep="$${KEEP:-}"; fi; \
	  log="$$dst.render.log"; \
	  echo "--- $$profile: rendering to $$dst"; \
	  if ! copier copy --overwrite --defaults --trust \
	    -d project_name=TestProject -d scaffold_full_project=true \
	    -d primary_backend_language=python -d primary_chat_agent=lg_agent \
	    -d include_agent_reference_library=false \
	    -d global_skills_source=none -d enable_macos_notifications=false \
	    $$extra $(input_dir) "$$dst" >"$$log" 2>&1; then \
	    echo "--- $$profile: render FAILED"; cat "$$log"; \
	    failed="$$failed $$profile(render)"; rm -f "$$log"; \
	    [ -n "$$keep" ] || rm -rf "$$dst"; continue; \
	  fi; \
	  rm -f "$$log"; \
	  if [ ! -f "$$dst/pyproject.toml" ]; then \
	    echo "--- $$profile: no pyproject.toml rendered — nothing to lint"; \
	    [ -n "$$keep" ] || rm -rf "$$dst"; continue; \
	  fi; \
	  if ( cd "$$dst" && uv sync --only-group dev --quiet && UV_NO_SYNC=1 $(MAKE) lint-check ); then \
	    echo "--- $$profile: lint-check OK"; \
	  else \
	    echo "--- $$profile: lint-check FAILED"; failed="$$failed $$profile"; \
	  fi; \
	  if [ -n "$$keep" ]; then echo "--- $$profile: kept at $$dst"; else rm -rf "$$dst"; fi; \
	done; \
	if [ -n "$$failed" ]; then echo; echo "lint-render FAILED for:$$failed"; exit 1; fi; \
	echo; echo "lint-render passed"

test:  ## Validate paths + catalog check
	@python3 tools/template/validate_paths.py
	@python3 tools/template/validate_paths.py --catalog-check

## Render the ML matrix entry to a real directory and run its pytest suite.
## validate_paths.py's run_render_tests() renders this same combination but only
## greps for unrendered Jinja before discarding the tree — the tests never run.
## Every ML step's Done-when command needs a rendered tree to run inside, so this
## target keeps the output and runs pytest in it.
## Usage: make test_render                 (renders to a temp dir, removes it after)
##        make test_render KEEP=1          (prints the path, leaves it in place)
##        make test_render DST=/some/path  (renders to a path you choose, keeps it)
##        make test_render PYTEST_ARGS="tests/unit/ml/test_transform.py -v"
##                                         (replaces the default pytest target)
test_render: check_tools
	@dst="$${DST:-$$(mktemp -d -t ait_render)}"; \
	keep="$${KEEP:-}"; [ -n "$${DST:-}" ] && keep=1; \
	echo "rendering to $$dst"; \
	copier copy --overwrite --defaults --trust \
	  -d project_name=TestProject -d scaffold_full_project=true \
	  -d primary_backend_language=python -d primary_chat_agent=lg_agent \
	  -d include_ml=true -d include_agent_reference_library=false \
	  -d global_skills_source=none -d enable_macos_notifications=false \
	  $(input_dir) "$$dst" >/dev/null || { echo "render FAILED"; rm -rf "$$dst"; exit 1; }; \
	( cd "$$dst" && uv sync --quiet && uv run pytest $${PYTEST_ARGS:-tests/unit/ml} ); \
	rc=$$?; \
	if [ -n "$$keep" ]; then echo "rendered tree kept at: $$dst"; else rm -rf "$$dst"; fi; \
	exit $$rc

check_tools:
	@command -v copier >/dev/null 2>&1 || { echo "copier not found — install with: uv tool install copier"; exit 1; }

## Apply this template into a new or existing project directory.
## Usage: make new_project output_dir="~/Workspace/my-project" project_name="My Project"
new_project: check_tools
	@$(MAKE) run_copier VCS_REF=""

## Same as new_project, but renders from the current dirty working tree
## instead of requiring a committed ref — useful while iterating on the template itself.
new_project_dev: check_tools
	@$(MAKE) run_copier VCS_REF="--vcs-ref HEAD"

run_copier:
	@output_dir=$${output_dir:-$$(read -p "output_dir (existing or new project path): " r && echo $$r)}; \
	project_name=$${project_name:-$$(read -p "project_name: " r && echo $$r)}; \
	mkdir -p "$$output_dir"; \
	output_dir=$$(cd "$$output_dir" && pwd); \
	copier copy $(VCS_REF) $(input_dir) "$$output_dir" --trust -d "project_name_input=$$project_name"

## Render a project from a genesis answers file produced by /new.
## Usage: make project ANSWERS=/tmp/genesis-answers.yml output_dir=~/workspace/my-project
##        make project ANSWERS=/tmp/genesis-answers.yml output_dir=~/workspace/my-project OVERWRITE=1
project: check_tools
	@answers=$${ANSWERS:-}; \
	if [ -z "$$answers" ]; then echo "ANSWERS is required — e.g. make project ANSWERS=/tmp/genesis-answers.yml output_dir=..."; exit 1; fi; \
	output_dir=$${output_dir:-$$(read -p "output_dir (target project path): " r && echo $$r)}; \
	mkdir -p "$$output_dir"; \
	output_dir=$$(cd "$$output_dir" && pwd); \
	overwrite_flag=$$([ -n "$${OVERWRITE}" ] && echo "--overwrite" || echo ""); \
	copier copy --vcs-ref HEAD --trust --defaults $$overwrite_flag --data-file "$$answers" $(input_dir) "$$output_dir"

## Preview resolved copier defaults without rendering any files.
## Usage: make preview_defaults project_type=rag external_systems="[slack,github]"
##        make preview_defaults ARGS="--all"
preview_defaults:
	@python3 tools/template/preview_defaults.py $(filter-out $@,$(MAKECMDGOALS)) $(ARGS)
