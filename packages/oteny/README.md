# oteny — author CLI

Account-key Talent authoring loop for OtenyBot. Install:

```bash
uv tool install "oteny @ git+https://github.com/otenycom/talents.git#subdirectory=packages/oteny"
# or editable:
uv pip install -e packages/oteny
```

```bash
oteny test --api-key-file ~/.oteny/account.key --ref hh0xxxx \
  --bundle my-talent --bundle-dir ./skills/my-talent --scenario happy_path
oteny traces --api-key-file ~/.oteny/account.key --ref hh0xxxx
oteny lint ./skills/my-talent
```

Requires an Oteny account API key. Business-bot Discuss scenarios also need the
bundle `tests/discuss.yaml` tester key file. Never uses Oteny staff control-plane keys.

Telegram DM transport is Phase 2. CLI/hermes oneshot transport is supported for
plain chat turns (not workflow `hand_off`).
