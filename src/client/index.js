const dotenv = require('dotenv');
const http = require('http');

dotenv.config();

const openrouterApiKey = process.env.OPENROUTER_API_KEY;

console.log('[Client] Client started.');
console.log('[Client] OPENROUTER_API_KEY loaded:', !!openrouterApiKey);

// Example: Send a GET request to the server root
const options = {
    hostname: 'localhost',
    port: 3000,
    path: '/',
    method: 'GET'
};

const req = http.request(options, res => {
    let data = '';
    res.on('data', chunk => {
        data += chunk;
    });
    res.on('end', () => {
        console.log('[Client] Server response:', data);
        process.exit(0);
    });
});

req.on('error', error => {
    console.error('[Client] Error connecting to server:', error.message);
    process.exit(1);
});

req.end();
