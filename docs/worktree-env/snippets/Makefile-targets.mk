# Worktree targets for the root Makefile.
# Copied from resslab-hub/Makefile (lines 14-15 and 64-95).
#
# Drop these into the target repo's root Makefile and add the target names to
# its .PHONY line. The db-* targets only make sense if the project has a
# PostgreSQL dev database; skip them otherwise (and skip wt-db.sh with them).

.PHONY: dev-all new go db-template-light db-template db-branch db-branch-full db-branch-drop db-status wt-land wt-done wt-open

# tmux session "<repo>/<branch>" with claude, backend, frontend and shell panes.
# Starts the database container if the project has one. Works in the main
# checkout and in every git worktree.
dev-all:
	scripts/tmux-dev.sh

# --- git worktrees
new:                    ## make new BRANCH=feat/x [BASE=origin/dev] [PROMPT=brief.md]  : worktree + deps + session, attached
	scripts/wt-new.sh $(BRANCH) $(BASE) $(if $(PROMPT),--prompt '$(PROMPT)')

go: new                 ## make go BRANCH=feat/x  : same thing, truthful verb: jump to the branch's session, creating branch/worktree/session as needed (tab completion: wtgo, scripts/wt-go.bash)

wt-land:                ## make wt-land BRANCH=feat/x [MODE=--local]  : rebase, PR + squash-merge into the base branch, clean up
	scripts/wt-land.sh $(BRANCH) $(MODE)

wt-done:                ## make wt-done BRANCH=feat/x  : kill the session + remove the worktree, keep the branch
	scripts/wt-done.sh $(BRANCH)

wt-open:                ## make wt-open [TARGET=frontend|backend] [BRANCH=feat/x]
	scripts/wt-open.sh $(or $(TARGET),frontend) $(BRANCH)

# --- per-branch databases (PostgreSQL projects only)
# Rename the template databases in scripts/wt-lib.sh first, and adapt the
# template-light build in wt-db.sh to how this project loads its dev data.
db-template-light:      ## build the small template database (schema + a slice of data)
	scripts/wt-db.sh template-light

db-template:            ## copy the shared dev DB into the full template
	scripts/wt-db.sh template

db-branch:              ## clone a template (light if it exists) into this worktree's own DB and turn migrations on
	scripts/wt-db.sh create

db-branch-full:         ## same, but force the full template
	scripts/wt-db.sh create full

db-branch-drop:         ## drop this worktree's DB and go back to the shared one
	scripts/wt-db.sh drop

db-status:
	scripts/wt-db.sh status
