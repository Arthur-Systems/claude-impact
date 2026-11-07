# Contributing

## First-time setup

Accept your GitHub collaborator invitation, then follow the clone instructions
in [README.md](README.md).

Read [the event ground rules](docs/ground-rules.md) before adding code or data.
AI coding assistants should also follow [CLAUDE.md](CLAUDE.md).

## Make a change

Start from the latest `main` and create a branch with a short, descriptive name:

```sh
git switch main
git pull --ff-only
git switch -c feature/describe-your-change
```

Make your changes, then review and commit the specific files you want to share:

```sh
git diff
git status --short
git add path/to/changed-file
git commit -m "Describe the change"
git push -u origin HEAD
```

Open a pull request on GitHub. Explain what changed, why, and how you checked it.
Ask a teammate to review it before merging.

There are no application build or test commands yet. Add them to the README
when application code is introduced.

## Local files and credentials

Keep API keys, passwords, private data, and real environment files out of Git.
If the app needs configuration, commit an `.env.example` with placeholder values
and document how to copy it to a local `.env` file.
