# Contributing

## Develop and test in docker

Use the docker images so your results match CI and your host stays clean.

1. Build the CI image from `docker/Dockerfile.ci` and tag it `agents-inc-ci`. Use `docker/Dockerfile.dev` for an interactive shell.
2. Run the full suite:

```bash
docker run --rm --network none -v "$PWD:/src:ro" agents-inc-ci bash -c 'cp -r /src ~/w && cd ~/w && python3 -m unittest discover -s tests -p "test_*.py"'
```

3. Run the stress check:

```bash
docker run --rm --network none -v "$PWD:/src:ro" -v "$PWD/docker/stress_check.sh:/stress.sh:ro" agents-inc-ci bash /stress.sh
```

A fix must work with no setup beyond `agents-inc install`. Without docker, run `python3 -m unittest discover -s tests -p 'test_*.py'` on Python 3.11 or later.

## Pull requests

Work on a feature branch. Open the PR against `development`. Never push to `main` or force-push.
