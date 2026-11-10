# Hosting a shared copy of James (free)

**Why:** so the whole team, the coach and RVL can open the prototype on their own laptop, with a login.
**Only fictitious data.** Never put real RVL reports or documents on a hosted copy (rule 4 and 6 in the README).

## What the app does for this
- Login is **off** on your own laptop (`start_james.bat` works as before).
- It switches **on** when the environment variable `JAMES_USERS` is set:
  `Ivan Hoornweg:password1;Tasnim:password2;Harm:password3`
  (name and password with a colon, people with a semicolon, no `:` or `;` inside a password).
- The name that signs a decision is always the logged-in name. The browser cannot sign as someone else.
- Sessions last 12 hours. After 5 wrong passwords from one address, that address waits a minute.
- On a hosting service (it sets `PORT`) the app **refuses to start without a login**.
- `JAMES_SECRET` signs the login cookie. Render generates it.
- Passwords are only in the hosting dashboard, never in the repository.

## Render with a disk (chosen option), step by step
About **$7.25 a month** (small server $7 + 1 GB disk $0.25), in the EU (Frankfurt). Prices as seen on 10 Nov 2026; Render changes them, so check before paying.
The repository is private and belongs to Tasnim, so **Tasnim** (the repo owner) connects it. One person puts a payment method on the account; the rest pays that person back.
1. Make an account at render.com and choose "Sign up with GitHub". Add a payment method.
2. New, then **Blueprint**, pick the repository `rvl_asbest` and the branch to deploy. Render reads `render.yaml`.
3. Render asks for `JAMES_USERS`. Fill in one name and password per person, like `Ivan Hoornweg:password1;Tasnim:password2`. Share the passwords personally, not in a group chat or in git.
4. Deploy. After a few minutes you get a link like `https://james.onrender.com`.
5. Everyone opens the link and logs in. The data (projects, decisions) is kept on the disk.

**Same, but free:** in `render.yaml` change `plan: starter` to `plan: free` and delete the `disk:` block and the `JAMES_DB` variable. Then the app sleeps after 15 minutes and forgets everything when it sleeps, restarts or is redeployed.

## Limits to know
- One copy of the app runs, because a disk belongs to one copy. A deploy takes the app offline for about a minute.
- All logged-in people share one "current project": if one picks another project, the other person's screen follows. Fix before several people work at the same time.
- The server handles one request at a time. Fine for a few people, not for daily use by a team.
- No back-ups yet. Check what Render offers for disks before relying on the data.
- No photo upload yet (only a reference like IMG_0101 is kept). A disk of 1 GB is enough for now.
- Free plan source: https://render.com/docs/free.

## Alternatives
- **Same wifi:** `python app\server.py --host 0.0.0.0` (it warns that there is no login unless `JAMES_USERS` is set). Often blocked on school wifi.
- **Tunnel:** ngrok or cloudflared in front of your own laptop. Needs your laptop on.
- **PythonAnywhere free:** one web app, expires after a month, needs a WSGI wrapper we have not built.

## For real use later
A hosted copy that keeps its data needs a paid plan with a disk or a database, a proper account system (password reset, hashing), and agreement from Rolf and the coach on where RVL data may live.
