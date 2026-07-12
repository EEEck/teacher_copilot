# Plan Workflow Feedback Design

## Goal

Make plan discard and save actions communicate their actual operation, and prevent
GPT-5.4-family utility calls from sending the unsupported `minimal` reasoning effort.

## Design

- Represent footer work as `idle`, `preparing`, or `discarding` instead of one
  ambiguous loading boolean. Discard remains visible and reads `Discarding...`
  until the fresh draft loads; it never shows save language.
- Keep the final review save action disabled after submission and show the shared
  spinning progress icon until the route changes or an error restores the action.
- Normalize `minimal` to `none` at agent model-settings construction only for
  GPT-5.4-family model identifiers. Preserve configured profile values and all
  other reasoning efforts.

## Verification

- Backend unit tests cover GPT-5.4 normalization and unchanged settings for other
  model families.
- Frontend tests cover the shared review button's disabled spinner state.
- Frontend type checking and focused backend/frontend tests must pass.
