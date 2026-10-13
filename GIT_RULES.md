# Git & Version Control Rules — ResumeRank (Two-Member Team) — MUST FOLLOW

These rules apply to the **entire repository, every branch, every task, and all future work** unless we both explicitly agree to change them.

The repository has exactly **two contributors**. Nobody else — human or AI — may ever appear in the Git history.

---

## 0. Team Identities and Ownership

| Role | Name | Git email | GitHub user | Owns (from the project blueprint) |
| --- | --- | --- | --- | --- |
| **Member A — Backend & AI Lead** | M. Lahari | laharisuresh6666@gmail.com | Lahari-66 | `lambda/process_resume/`, Textract + Comprehend integration, `skills.json`, `scoring.py`, DynamoDB writes, SNS publish, custom metric, technical report sections |
| **Member B — API, Frontend & Ops Lead** | S. Mounika Reddy | sherymounikareddy.2006@gmail.com | Mounika-Reddy-0802 | `lambda/api_handler/`, `frontend/`, `iam/` policies, API Gateway config notes, test resumes, CloudWatch dashboard, architecture diagram, README and report assembly |
| **Shared** | both | — | — | `INTERFACES.md`, `docs/test_matrix.md`, `docs/report/` final merge, `README.md` final pass |

**Every commit is made and pushed from the GitHub account of the person who did that work.** Lahari's work is committed as Lahari from Lahari-66; Mounika's work is committed as Mounika from Mounika-Reddy-0802. Never commit the other person's work under your name, and never let the other person commit your work under theirs.

---

## 1. No Claude or AI Attribution — STRICT RULE

**NEVER add Claude or any AI assistant as a GitHub contributor, author, co-author, committer, or Git identity.**

In particular:

* Never add `Co-authored-by: Claude` or any AI trailer.
* Never add any AI tool's username or email to commits.
* Never configure an AI tool as a Git author or committer.
* Never allow AI attribution to appear in commit metadata.
* Never intentionally create commits that show an AI alongside either of our GitHub identities.
* Never allow an AI to appear as a contributor through commit attribution.

Before every commit, verify the **author, committer, and commit trailers**.

**All commits must use only the two identities in Section 0.**

This is a permanent rule for the **whole repository**, not just the current branch.

---

## 2. Git Identity Setup — Do This Before the First Commit

### Option A — each person works on their own laptop (preferred)

Each person clones the repo once and sets a **repo-local** identity (not `--global`, so nothing leaks into other projects):

```bash
# Lahari
git config user.name  "M. Lahari"
git config user.email "laharisuresh6666@gmail.com"

# Mounika
git config user.name  "S. Mounika Reddy"
git config user.email "sherymounikareddy.2006@gmail.com"
```

### Option B — both work on the same machine

Keep **two separate clones**, one per person, each with its own local identity and its own remote URL that includes the GitHub username so the credential helper keeps the two logins apart:

```bash
# Lahari's clone
git clone https://Lahari-66@github.com/<org-or-user>/resumerank.git resumerank-lahari
cd resumerank-lahari
git config user.name  "M. Lahari"
git config user.email "laharisuresh6666@gmail.com"

# Mounika's clone
git clone https://Mounika-Reddy-0802@github.com/<org-or-user>/resumerank.git resumerank-mounika
cd resumerank-mounika
git config user.name  "S. Mounika Reddy"
git config user.email "sherymounikareddy.2006@gmail.com"
```

Never commit from the wrong clone. Before committing, run `git config user.email` and read the answer.

### Verify identity before every commit

```bash
git config user.name && git config user.email
git log -1 --format='%an <%ae> | %cn <%ce>%n%B'   # after committing: author, committer, trailers
```

If the author or committer is wrong, fix it **before pushing**:

```bash
git commit --amend --reset-author --no-edit
```

---

## 3. Personal Access Tokens (PATs) — Handling Rules

Each person uses **their own** fine-grained PAT, scoped to this one repository with `Contents: Read and write` only.

* **Never commit a PAT.** Not in `.env`, not in `.git/config`, not in a script, not in a README, not in a Lambda environment file, not in a comment.
* **Never put a PAT in `.git/` by hand.** The remote URL must not contain the token (`https://TOKEN@github.com/...` is forbidden because `.git/config` can get copied or shared).
* Store the token in the OS credential manager through Git's credential helper, once per clone:

  ```bash
  git config credential.helper manager     # Windows (Git Credential Manager)
  git config credential.helper osxkeychain # macOS
  git config credential.helper store       # Linux: stores in ~/.git-credentials, outside the repo
  ```

  On the first `git push`, enter your GitHub username and paste the PAT as the password. It is remembered for that clone's remote URL only.
* If a `.env` file is used at all, it holds only **AWS-side** values needed locally (region, bucket names, table names) and is listed in `.gitignore`. It never holds a GitHub token or AWS keys.
* `.gitignore` must contain, from the first commit:

  ```
  .env
  .env.*
  *.pem
  *.key
  **/credentials
  **/aws-credentials*
  __pycache__/
  *.zip
  node_modules/
  .DS_Store
  ```
* If a token is ever committed by mistake: revoke it on GitHub **immediately**, generate a new one, then remove it from history (Section 10). Rotating is mandatory; removing from history is not a substitute.
* Each PAT belongs to exactly one person. Never share a PAT, never push with the other person's token, never store both tokens in one clone.

---

## 4. Meaningful Commits Only

Do **not** create commits for every tiny change.

A commit should have **real weight** and represent a meaningful unit of work, such as:

* A completed Lambda function or a completed stage inside one (e.g. Textract integration working end-to-end)
* A completed API route set
* A working frontend page
* A completed IAM policy set
* The skill dictionary plus the scoring module together
* The CloudWatch dashboard definition plus its screenshots
* A finished report section or the architecture diagram
* A coherent group of related fixes found during the six-resume test run

Avoid meaningless commits such as:

* Fix one small line
* Change one sentence
* Minor formatting
* Tiny documentation correction
* Small import cleanup
* One insignificant file change
* Repeated "fix", "update", or "change" commits for the same piece of work

**Group related changes together and commit them as one meaningful unit.**

### Core principle

> **Fewer, stronger, meaningful commits are better than many small, meaningless commits.**

Before committing, ask:

> **"Does this commit represent meaningful work that is worth appearing in the project's Git history?"**

If the answer is no, **do not commit yet**. Continue working and group it with related work.

---

## 5. Do Not Artificially Split Work — and Do Not Mix Owners

Do not split one meaningful feature into many tiny commits just to increase the commit count.

For example, if the Textract integration requires:

* the start/poll loop in the Lambda
* a helper to join LINE blocks
* a log line for the text preview
* a note in the README

and these belong to the same completed feature, they are **one coherent commit by Lahari**.

At the same time:

* Do not put completely unrelated work into the same commit.
* **Do not put one person's files into the other person's commit.** If Mounika's frontend change and Lahari's Lambda change were made in the same hour, they are two commits by two people, not one.
* Shared files (`INTERFACES.md`, `docs/test_matrix.md`) are committed by whoever made the agreed change, after the other person has seen it.

The goal is:

**Meaningful + coherent + reviewable commits, each clearly belonging to its owner.**

---

## 6. Every Meaningful Completed Change Must Be Committed and Pushed by Its Owner

When a meaningful piece of work is completed:

1. Finish the implementation.
2. Verify that the project still works (run the Lambda test event / open the page / run curl against the API).
3. Review the changed files.
4. Check that only intended changes — and only **your** files — are included.
5. Verify your Git identity (`git config user.email`).
6. Create one meaningful, focused commit.
7. Push it to GitHub **from your own account**.
8. Tell the other person what was pushed (one line in chat).
9. Then proceed to the next meaningful task.

Do not leave completed meaningful work uncommitted indefinitely. In particular, **all code must be pushed at the end of every hour-block of the blueprint** so that nothing lives only on one laptop.

---

## 7. Commit Messages

Commit messages must be:

* Short
* Natural
* Human-written
* Clear
* Specific
* Lowercase where appropriate
* Focused on the actual change
* Around 50 characters when practical

Avoid artificial or AI-style commit messages such as:

* `Implement comprehensive serverless architecture`
* `Refactor pipeline architecture`
* `Introduce advanced AI functionality`
* `Enhance robust processing pipeline`
* `Complete implementation of...`
* `Add extensive improvements`
* `Improve overall system`
* `Optimize cloud infrastructure`

Prefer natural developer-style messages such as:

* `add process_resume lambda skeleton`
* `add textract async polling`
* `add comprehend entity extraction`
* `add skill dictionary and scoring`
* `write candidate score to dynamodb`
* `send sns alert above threshold`
* `add api handler with three routes`
* `add presigned upload url`
* `add upload page`
* `add recruiter leaderboard page`
* `fix cors on api gateway`
* `add iam policies`
* `add test resumes and expected scores`
* `add cloudwatch dashboard`
* `add architecture diagram`
* `update readme deploy steps`
* `add report sections`

The commit message should describe **what actually changed**, not exaggerate the work.

---

## 8. Verify Before Every Commit

Before creating a commit:

* Check `git status`.
* Review the changed files.
* Review the actual diff (`git diff --staged`).
* Make sure unrelated files are not included.
* Make sure the other person's files are not included.
* Make sure **no secrets or credentials** are being committed — no PAT, no AWS access key, no `.env`, no `credentials` file, no Lambda zip with secrets inside.
* Verify the project is in a working state when practical.
* Verify the Git author and committer identity is **yours**.
* Verify there is **no Claude/AI attribution**.

Do not blindly commit everything in the working directory. `git add .` is allowed only after `git status` has been read.

---

## 9. Push and Branch Rules

* Always use the **one existing shared repository** and your **own configured credentials**.
* Do not create another repository.
* Do not switch to another GitHub account. Lahari pushes only as Lahari-66; Mounika pushes only as Mounika-Reddy-0802.
* Do not change the Git remote unless both of us agree.
* Work on `main` directly for this 2-day project; it is short enough that feature branches add more cost than safety. If a branch is ever needed, name it `lahari/<topic>` or `mounika/<topic>` so ownership is visible.
* Always `git pull --rebase` before pushing, so the two tracks interleave cleanly without merge commits.
* Never force-push unless both of us explicitly agree or an approved history-rewrite (Section 10) requires it.
* Do not merge or rewrite branch history unless required for the task and agreed by both.
* Tag the final state as `v1.0` from whichever account makes the last commit, after both have reviewed.

---

## 10. History-Rewrite Rule

If Git history needs to be rewritten (wrong author, accidental secret, AI trailer slipped in):

* Do not change the actual project code or file contents unless explicitly requested.
* Preserve the original commit structure whenever possible.
* Preserve the original author dates.
* Preserve the original committer dates.
* Do not make historical commits appear as if they were created today.
* Correct the author/committer to the right one of our two identities.
* Remove unwanted author/co-author/committer metadata as required.
* Never introduce any AI attribution while rewriting history.
* Verify the rewritten history before force-pushing (`git log --format='%h %an <%ae> %ad' --date=short`).
* Both of us must agree before any force-push, and the other person must re-clone or hard-reset afterwards.

For an approved history rewrite, the objective is:

**Same project content + same meaningful commit timeline + corrected Git metadata, with only our two identities.**

---

## 11. Final Permanent Rule

These rules apply to **everything we do in this repository from now on**.

The priorities are:

**1. No AI attribution anywhere.**
**2. Each person commits and pushes their own work from their own account.**
**3. No PAT, AWS key or `.env` is ever committed.**
**4. Meaningful commits only.**
**5. Group related work instead of creating tiny commits.**
**6. Keep commit history clean, natural, and professional.**
**7. Verify identity and changes before committing.**
**8. Push completed work to the one shared repository at the end of every block.**

### Most important rule

> **Never add Claude or any AI as a contributor, co-author, author, committer, or Git attribution — never push the other person's work under your name — and never create meaningless commits just to increase the commit count.**
