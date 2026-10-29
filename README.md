# Degree Desk — HEC Attestation Assistant

An independent AI assistant that helps users understand common Higher Education
Commission (HEC) degree attestation questions in Pakistan. It is not an official
HEC service and does not determine application status.

## Deploy to Vercel

1. Push this repository to GitHub and import it as a project in Vercel. Keep the
   project root set to the repository root.
2. In **Project Settings → Environment Variables**, add:
   - `XAI_API_KEY` — your **Groq** API key (use this exact variable name;
     keep it server-side and never add it to frontend code or commit it).
   - `GROQ_MODEL` — optional default selection; defaults to `openai/gpt-oss-20b`.
3. Apply the variables to the environments you plan to use and deploy (or
   redeploy) the project.
4. Open the deployed site. The connection indicator checks the Groq key and
   configured model; ask a question to test the chat.

The model picker offers the six text chat models currently listed in Groq's
free-plan rate limits: GPT OSS 20B, GPT OSS 120B, Qwen 3.8 27B, GPT OSS
Safeguard 20B, and Llama Prompt Guard 2 (22M and 86M). The safety models are
specialized classifiers, not general-purpose assistants. The list is checked
against Groq's live model catalog when the page loads. Audio transcription and
speech-generation models use different API endpoints and are not chat options.
Free availability and limits can change; check Groq's current
[model catalog](https://console.groq.com/docs/models) and
[rate limits](https://console.groq.com/docs/rate-limits). The function reads
the API key only from the server environment and does not return it to visitors.

## Run locally

Python 3.12 is recommended. In PowerShell, from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set your real Groq API key as `XAI_API_KEY` in the local `.env` file. The
variable name is retained for compatibility with the Vercel setting; the key
value itself must come from Groq, not xAI. Do not commit that file.
Use Vercel's local development server to exercise both the static page and API:

```powershell
npx vercel dev
```

## Endpoints

- `GET /api` checks that the key is accepted and the configured model is
  available to the account.
- `POST /api` accepts JSON in the form `{"message":"Your question"}`.

The API limits requests to 4,000 message characters. Groq credentials and
provider response details are kept out of the browser response. The chat
endpoint is public and does not require user sign-in, so keep the free-tier
account limits in mind when sharing the deployed site. User messages are sent
to Groq to generate replies; users should not submit sensitive personal data.
