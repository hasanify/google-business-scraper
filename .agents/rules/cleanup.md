---
trigger: always_on
---

# Temporary File and Directory Cleanup Policy

You must aggressively clean up all temporary files, directories, caches, artifacts, generated resources, intermediate outputs, and transient working data created during task execution.

This is a mandatory operational requirement.

## Core Rule

After completing the task, the environment must be left in a clean state with no unnecessary temporary resources remaining.

Anything created solely for intermediate processing, debugging, downloading, extraction, compilation, conversion, testing, staging, logging, or caching must be removed automatically before finishing.

## Cleanup Scope

You must remove all of the following if created during execution:

- Temporary directories
- Scratch workspaces
- Downloaded archives
- Extracted folders
- Build artifacts
- Compilation outputs
- Cache directories
- Generated logs
- Temporary databases
- Intermediate JSON/CSV/TXT files
- Temporary images/audio/video
- Cloned repositories used only during execution
- Virtual environments created temporarily
- Package caches
- Test outputs
- Session artifacts
- Lock files created only for transient work
- Debugging files
- Temporary configuration files
- Converted intermediate assets

## Required Behavior

### 1. Track Temporary Resources

Maintain an internal list of every temporary file and directory created during execution.

Every creation step must be paired with a cleanup step.

### 2. Prefer Isolated Workspaces

Use isolated temporary working directories for transient operations so cleanup is deterministic.

Examples:

- `mktemp`
- isolated sandbox folders
- scoped temp workspaces

Avoid scattering temporary files across the filesystem.

### 3. Cleanup Must Execute Even on Failure

Cleanup logic must run regardless of:

- task success
- partial failure
- interruption
- exception
- timeout
- retry

Use finally/defer/trap cleanup patterns where applicable.

Examples:

- `try/finally`
- `defer`
- `trap EXIT`
- shutdown hooks
- destructor patterns

### 4. Verify Cleanup

After cleanup:

- verify temporary paths no longer exist
- verify no orphaned processes hold file handles
- verify disk usage from temporary artifacts is removed

### 5. Preserve Only Required Deliverables

Do not delete:

- explicitly requested output files
- final deliverables
- user-owned existing files
- persistent project assets unless instructed

Everything else must be removed.

## Safety Constraints

Never recursively delete paths unless absolutely certain they were created during the current task.

Before deletion:

- validate target paths
- avoid unsafe wildcard expansion
- prevent accidental parent directory deletion
- never execute destructive cleanup on ambiguous paths

Forbidden examples:

- `rm -rf /`
- deleting user home directories
- deleting shared workspace roots
- deleting repositories not created during the task

## Logging

Cleanup operations should be concise and explicit.

Log:

- what was removed
- what was preserved
- whether cleanup completed successfully

Do not leave silent residual artifacts.

## Completion Requirement

A task is not considered complete until cleanup has successfully executed.

The final state should contain only:

- requested deliverables
- intentionally persistent project files
- explicitly preserved artifacts

Everything else must be removed automatically.
