# Docker fallback publish (run after Docker Desktop is installed)

Image name used in submission docs: `nishadmahmud/elec-bup:v1`

```powershell
cd C:\Users\Nishad\Desktop\WEB\BUP_HACKATHON

docker build -t nishadmahmud/elec-bup:v1 .
docker login
docker push nishadmahmud/elec-bup:v1

# Verify locally (do not bake secrets into the image)
docker run --rm -p 8000:8000 -e OPENAI_API_KEY=$env:OPENAI_API_KEY -e OPENAI_MODEL=gpt-4o-mini nishadmahmud/elec-bup:v1
curl http://127.0.0.1:8000/health
```

Organizer fallback:

```powershell
docker pull nishadmahmud/elec-bup:v1
docker run --rm -p 8000:8000 -e OPENAI_API_KEY=<KEY> -e OPENAI_MODEL=gpt-4o-mini nishadmahmud/elec-bup:v1
```
