# Example fixtures

`sample-monorepo/` is an intentionally tiny synthetic workspace. Its `pnpm-workspace.yaml`, package manifests, TypeScript files, and folders exercise basic multi-service detection. It is not a working app and does not install dependencies.

Preview it without modifying any files:

```bash
python3 repomoor.py examples/sample-monorepo --json
python3 repomoor.py examples/sample-monorepo --doctor
```

If you want to test `--apply`, copy the sample into a disposable temporary directory first so this example fixture remains clean:

```bash
mkdir -p /tmp/repomoor-demo
cp -R examples/sample-monorepo/. /tmp/repomoor-demo/
python3 repomoor.py /tmp/repomoor-demo --apply --integrate --json
```

`/tmp` is a POSIX example; use a different disposable directory on Windows.
