const dotenv = require('dotenv');
const http = require('http');

dotenv.config();

const openrouterApiKey = process.env.OPENROUTER_API_KEY;

console.log('[TestClient] Test client started.');
console.log('[TestClient] OPENROUTER_API_KEY loaded:', !!openrouterApiKey);

// Test GET /
function testRootEndpoint() {
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
            console.log('[TestClient] GET / response:', data);
            testPostExample();
        });
    });

    req.on('error', error => {
        console.error('[TestClient] Error connecting to server (GET /):', error.message);
        process.exit(1);
    });

    req.end();
}

// Test POST /example (replace with your actual endpoint)
function testPostExample() {
    const postData = JSON.stringify({ message: 'Hello from test client!' });

    const options = {
        hostname: 'localhost',
        port: 3000,
        path: '/example',
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(postData),
            'Authorization': `Bearer ${openrouterApiKey}`
        }
    };

    const req = http.request(options, res => {
        let data = '';
        res.on('data', chunk => {
            data += chunk;
        });
        res.on('end', () => {
            console.log('[TestClient] POST /example response:', data);
            console.log('[TestClient] All tests complete.');
            process.exit(0);
        });
    });

    req.on('error', error => {
        console.error('[TestClient] Error connecting to server (POST /example):', error.message);
        process.exit(1);
    });

    req.write(postData);
    req.end();
}

// Start tests
testRootEndpoint();
