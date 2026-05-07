const https = require('https');

const apiKey = "am_us_f25361faa1077ccfcdd0dfb13d972965b55b0920c5fdbb35254b3dbbc501c26e";
const inboxId = "excitedsilver931@agentmail.to";

const options = {
  hostname: 'api.agentmail.to',
  port: 443,
  path: `/v0/inboxes/${encodeURIComponent(inboxId)}/messages?limit=5&ascending=false`,
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${apiKey}`
  }
};

const req = https.request(options, (res) => {
  let data = '';
  res.on('data', (chunk) => { data += chunk; });
  res.on('end', () => {
    try {
      const json = JSON.parse(data);
      const messages = json.results || json;
      console.log(`Found ${messages.length} messages`);
      messages.forEach((msg, i) => {
        console.log(`${i+1}. ${msg.subject || 'No subject'}`);
      });
    } catch (e) {
      console.log('Error:', data);
    }
  });
});

req.on('error', (e) => console.error('Error:', e.message));
req.end();