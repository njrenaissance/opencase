## Summary

Briefly describe what this PR does and why. Link to the related issue(s), if
any.

## Type of Change

- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] Feature (non-breaking change adding functionality)
- [ ] Documentation
- [ ] Refactoring (code cleanup, no functional change)
- [ ] Chore (dependency updates, config changes, etc.)

## Related Issue(s)

Closes #(issue number)

## Testing

Describe how you tested this change:

- [ ] Unit tests added / updated
- [ ] Integration tests added / updated
- [ ] Manual testing (describe steps)
- [ ] No new tests needed (explain why)

## Non-Negotiables Checklist

Before submitting, please confirm:

- [ ] All vector queries limited to matter scope via
  `build_permissions_filter()` (if modifying RAG/search)
- [ ] No new third-party LLM API calls introduced
- [ ] No external telemetry (all observability stays local)
- [ ] No client data sent outside the container
- [ ] Legal hold constraints respected (if modifying document deletion)
- [ ] Audit logging in place (if modifying data access, permissions, or LLM
  queries)
- [ ] Encryption at rest/transit not bypassed
- [ ] No plaintext storage of sensitive data

## Other Notes

Any additional context for reviewers, architectural decisions, tradeoffs, or
potential follow-up work.
