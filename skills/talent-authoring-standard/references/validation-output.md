# Validation output (what the grader returns)

When validating a Talent bundle against the 12-check rubric in
[`../SKILL.md`](../SKILL.md), emit a compact verdict — nothing else:

```
BUNDLE: <path>   (<n> composing skills)
1 structure        PASS
2 goal-defined     PASS
3 first-run        FAIL — section has a judgement call ("decide the schema") at line 88; make it literal
4 pii-clean        PASS
5 routing          FAIL — no channel_prompt declared in agent-profile.yaml
6 namespacing      PASS
7 safety           N/A — n/a for this domain? confirm
8 localization     PASS
9 tools/stubs      PASS
10 discovery       PASS
11 weak-model-ops  FAIL — no master triage; meal handling is prose, not an entry→analysis→reply checklist
12 upgrade-safe    PASS

VERDICT: FIX-FIRST  (3 blocking: #3, #5, #11)
MUST-FIX: <one line each>
```

A bundle ships only at **VERDICT: SHIP** (no FAILs; N/As justified).
