# POS Lv2 Backend Deployment Notes

## Azure App Service (Linux) Startup Command

When deploying this FastAPI backend to Azure App Service (Linux), configure the **Startup Command** field in the Azure portal with the following value so that Gunicorn manages Uvicorn workers:

```
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app.main:app
```

After deployment, verify the health endpoint responds with `{"status":"ok"}` by visiting:

```
https://app-002-gen10-step3-1-py-oshima51.azurewebsites.net/api/health
```
