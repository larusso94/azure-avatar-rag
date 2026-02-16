# Frontend Configuration Guide

## Azure Speech Services Setup

The avatar requires Azure Speech Services credentials to work. You need to update the HTML file with your own credentials.

### Steps:

1. **Get your Azure Speech credentials:**
   - Go to [Azure Portal](https://portal.azure.com)
   - Navigate to your Speech Service resource
   - Copy the **Key** and **Region**

2. **Update `index.html`:**

Open `index.html` and find these lines (around line 17-19):

```html
<input id="region" type="hidden" value="YOUR_AZURE_REGION" />
<input id="APIKey" type="hidden" value="YOUR_AZURE_SPEECH_KEY" />
```

Replace:
- `YOUR_AZURE_REGION` with your region (e.g., `swedencentral`, `eastus`, `westeurope`)
- `YOUR_AZURE_SPEECH_KEY` with your Speech Service API key

### Example:

```html
<input id="region" type="hidden" value="eastus" />
<input id="APIKey" type="hidden" value="abc123...your-actual-key" />
```

### Security Note:

⚠️ **Important:** This configuration exposes your API key in the frontend code. For production use, you should:

1. **Use a backend proxy:** Route avatar requests through your backend API
2. **Implement token authentication:** Use Azure Speech SDK token endpoint
3. **Set up API key rotation:** Regularly rotate your Speech Service keys
4. **Use Azure Key Vault:** Store secrets securely and fetch at runtime

### Alternative: Backend Proxy (Recommended for Production)

Instead of hardcoding credentials in the frontend, implement a `/api/speech-token` endpoint in `app.py`:

```python
@app.route('/api/speech-token', methods=['GET'])
def get_speech_token():
    """Generate Azure Speech token for frontend."""
    from azure.cognitiveservices.speech import SpeechConfig
    
    speech_config = SpeechConfig(
        subscription=config.speech_key,
        region=config.speech_region
    )
    
    token = speech_config.get_authorization_token()
    
    return jsonify({
        "token": token,
        "region": config.speech_region
    })
```

Then update `js/basic.js` to fetch the token instead of using a hardcoded key.
