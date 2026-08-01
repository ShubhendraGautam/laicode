# Continuous integration and nightly evidence

LAIcode uses two GitHub Actions workflows. They deliberately separate ordinary
correctness checks from noisy hardware evidence.

## Required CI

`.github/workflows/ci.yml` runs on every pull request, every push to `main`, and
manual dispatch. It executes the complete test suite on:

- Python 3.10, the minimum supported interpreter; and
- Python 3.14, the current compatibility target.

Both jobs run on Ubuntu 24.04 with a C compiler available, so the generated-C,
cross-language comparator, and hardware-feedback integration tests execute
instead of silently skipping. The jobs have a 20-minute timeout.

Repository branch protection should require both checks:

```text
CI / Tests (Python 3.10)
CI / Tests (Python 3.14)
```

## Nightly study

`.github/workflows/nightly.yml` runs every day at 02:17 UTC and can also be
started manually from the Actions tab. It:

1. records the Python, C, GCC, Clang, and Node toolchains;
2. runs the complete repository test suite;
3. runs the default five-session `smoke-hardware-feedback` study; and
4. grows, replays, compiles, and validates the A0 algorithm language;
5. grows, replays, compiles, and validates the A1 owned-collection language;
   and
6. uploads the complete hardware, algorithm, and collection evidence for 30
   days.

The unusual minute avoids the common load spike at the top of the hour. A
nightly result is exploratory evidence tied to that ephemeral runner's pinned
target identity. It is not a stable performance baseline and does not deploy a
vocabulary.

## Security and maintenance

Both workflows declare only `contents: read`, disable persisted checkout
credentials, set explicit timeouts, and use concurrency controls. External
actions are pinned to full commit identities, with their reviewed release tags
left as comments. Dependabot checks GitHub Actions dependencies weekly so pin
updates arrive as reviewable pull requests.

No workflow uses `pull_request_target`, repository secrets, package publishing,
or write authority. Nightly artifacts contain deterministic synthetic programs,
generated runners, compiled artifacts, and benchmark evidence; they must not be
treated as deployable releases.

## Local equivalent

Run the same correctness command before pushing:

```sh
python3 -m unittest discover -v
```

Run the nightly research path locally with a fresh output location:

```sh
python3 -m laicode smoke-hardware-feedback /tmp/laicode-nightly
python3 -m laicode smoke-algorithm-language /tmp/laicode-algorithm-nightly
python3 -m laicode smoke-collection-language /tmp/laicode-collection-nightly
```
