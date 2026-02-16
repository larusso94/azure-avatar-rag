# Deployment Guide

## Azure Resources Setup

### 1. Azure OpenAI

```bash
# Create resource
az cognitiveservices account create \
  --name your-openai-resource \
  --resource-group your-rg \
  --location swedencentral \
  --kind OpenAI \
  --sku S0

# Deploy models
az cognitiveservices account deployment create \
  --resource-group your-rg \
  --name your-openai-resource \
  --deployment-name gpt-5-mini-deployment \
  --model-name gpt-5-mini \
  --model-version 2024-02-15 \
  --sku-capacity 10 \
  --sku-name Standard

az cognitiveservices account deployment create \
  --resource-group your-rg \
  --name your-openai-resource \
  --deployment-name text-embedding-3-large \
  --model-name text-embedding-3-large \
  --model-version 1 \
  --sku-capacity 10 \
  --sku-name Standard
```

### 2. Azure Speech Services

```bash
az cognitiveservices account create \
  --name your-speech-resource \
  --resource-group your-rg \
  --location swedencentral \
  --kind SpeechServices \
  --sku S0
```

### 3. Azure Cosmos DB

```bash
# Create account with NoSQL API
az cosmosdb create \
  --name your-cosmos-account \
  --resource-group your-rg \
  --locations regionName=swedencentral failoverPriority=0 \
  --default-consistency-level Session \
  --enable-free-tier false

# Create database
az cosmosdb sql database create \
  --account-name your-cosmos-account \
  --resource-group your-rg \
  --name avatarrag

# Create containers
az cosmosdb sql container create \
  --account-name your-cosmos-account \
  --database-name avatarrag \
  --name knowledge_base \
  --partition-key-path "/id" \
  --throughput 400

az cosmosdb sql container create \
  --account-name your-cosmos-account \
  --database-name avatarrag \
  --name sessions \
  --partition-key-path "/id" \
  --throughput 400
```

### 4. Get Credentials

```bash
# OpenAI
az cognitiveservices account show \
  --name your-openai-resource \
  --resource-group your-rg \
  --query properties.endpoint -o tsv

az cognitiveservices account keys list \
  --name your-openai-resource \
  --resource-group your-rg \
  --query key1 -o tsv

# Speech
az cognitiveservices account keys list \
  --name your-speech-resource \
  --resource-group your-rg \
  --query key1 -o tsv

# Cosmos DB
az cosmosdb keys list \
  --name your-cosmos-account \
  --resource-group your-rg \
  --type keys \
  --query primaryMasterKey -o tsv
```

---

## Deployment Options

### Option 1: Azure Container Apps (Recommended)

#### Build and Push Container
```bash
# Build image
docker build -t avatarrag:latest .

# Tag for ACR
docker tag avatarrag:latest yourregistry.azurecr.io/avatarrag:latest

# Push to ACR
az acr login --name yourregistry
docker push yourregistry.azurecr.io/avatarrag:latest
```

#### Deploy Container App
```bash
az containerapp create \
  --name avatar-rag-app \
  --resource-group your-rg \
  --environment your-container-env \
  --image yourregistry.azurecr.io/avatarrag:latest \
  --target-port 5000 \
  --ingress external \
  --env-vars \
    AZURE_OPENAI_ENDPOINT=secretref:openai-endpoint \
    AZURE_OPENAI_API_KEY=secretref:openai-key \
    COSMOS_ENDPOINT=secretref:cosmos-endpoint \
    COSMOS_KEY=secretref:cosmos-key
```

### Option 2: Azure App Service

```bash
# Create App Service Plan
az appservice plan create \
  --name avatar-rag-plan \
  --resource-group your-rg \
  --sku B1 \
  --is-linux

# Create Web App
az webapp create \
  --name avatar-rag-webapp \
  --resource-group your-rg \
  --plan avatar-rag-plan \
  --runtime "PYTHON:3.11"

# Configure environment variables
az webapp config appsettings set \
  --name avatar-rag-webapp \
  --resource-group your-rg \
  --settings @appsettings.json

# Deploy code
az webapp up \
  --name avatar-rag-webapp \
  --resource-group your-rg \
  --runtime "PYTHON:3.11"
```

### Option 3: Azure Kubernetes Service (AKS)

See `k8s/` directory for manifests.

---

## Cost Estimation

### Monthly Costs (USD, approximate)

| Service | Tier | Usage | Cost |
|---------|------|-------|------|
| Azure OpenAI | Standard | 1M tokens/month | ~$20 |
| Text Embeddings | Standard | 100K docs | ~$5 |
| Speech Services | Standard | 10K requests | ~$15 |
| Cosmos DB | Provisioned 400 RU/s | 2 containers | ~$25 |
| Container Apps | Consumption | 50K requests | ~$10 |
| **Total** | | | **~$75/month** |

### Cost Optimization Tips

1. **Use Cosmos DB Serverless** for dev/test
2. **Enable auto-scaling** for Container Apps
3. **Implement caching** for embeddings
4. **Use batch processing** for document uploads
5. **Monitor with Azure Monitor** and set budget alerts

---

## Monitoring & Observability

### Application Insights

```bash
# Create Application Insights
az monitor app-insights component create \
  --app avatar-rag-insights \
  --location swedencentral \
  --resource-group your-rg

# Get instrumentation key
az monitor app-insights component show \
  --app avatar-rag-insights \
  --resource-group your-rg \
  --query instrumentationKey -o tsv
```

### Metrics to Track
- API response times
- Document processing latency
- Vector search performance
- Token usage and costs
- Error rates by endpoint

---

## Security Considerations

### Managed Identity (Recommended)

```bash
# Enable managed identity on Container App
az containerapp identity assign \
  --name avatar-rag-app \
  --resource-group your-rg \
  --system-assigned

# Grant permissions to Key Vault
az keyvault set-policy \
  --name your-keyvault \
  --object-id <managed-identity-id> \
  --secret-permissions get list
```

### Network Security

- Use Virtual Network integration
- Enable Private Endpoints for Cosmos DB
- Implement Azure Front Door for WAF
- Use Azure Key Vault for secrets

---

## Troubleshooting

### Common Issues

**Issue: Cosmos DB connection timeout**
```bash
# Check firewall rules
az cosmosdb show \
  --name your-cosmos-account \
  --resource-group your-rg \
  --query ipRules
```

**Issue: OpenAI rate limits**
```python
# Implement retry with exponential backoff
from tenacity import retry, wait_exponential

@retry(wait=wait_exponential(multiplier=1, min=4, max=60))
def call_openai_api():
    # Your API call
    pass
```

**Issue: Large document processing fails**
```python
# Increase chunk size or implement streaming
CHUNK_SIZE = 1000  # Increase from 500
```

---

## CI/CD Pipeline

### GitHub Actions Example

```yaml
name: Deploy to Azure

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Azure Login
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
      
      - name: Build and Push
        run: |
          docker build -t avatarrag:${{ github.sha }} .
          docker push yourregistry.azurecr.io/avatarrag:${{ github.sha }}
      
      - name: Deploy to Container App
        run: |
          az containerapp update \
            --name avatar-rag-app \
            --resource-group your-rg \
            --image yourregistry.azurecr.io/avatarrag:${{ github.sha }}
```
