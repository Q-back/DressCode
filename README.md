# DressCode

DressCode is a CLI that remembers the mistakes an AI coding agent actually makes, hands them back as questions after every implementation, and tracks each entry statistics (how many times it was useful). Status: design only, nothing implemented yet; the shape lives in `openspec/changes/add-dresscode-cli/`.


## Boundaries

DressCode is a pure CLI over a state file plus git. It never spawns agents, never calls a model, never edits code. Triggering a review is the job of the companion `nanny` pi extension (separate repo at `/Users/opera_user/HomeProjects/nanny`) and of `pre-commit`.
