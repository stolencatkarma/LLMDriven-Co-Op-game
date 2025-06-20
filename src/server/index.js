const dotenv = require('dotenv');
const express = require('express');

dotenv.config();

const openrouterApiKey = process.env.OPENROUTER_API_KEY;

if (!openrouterApiKey) {
    console.warn('[Server] Warning: OPENROUTER_API_KEY is not set in environment variables.');
} else {
    console.log('[Server] OPENROUTER_API_KEY loaded from environment.');
}

const app = express();

app.use(express.json()); // Add this to parse JSON bodies

app.use((req, res, next) => {
    console.debug(`[Server] ${req.method} ${req.url} - ${new Date().toISOString()}`);
    next();
});

// Example route
app.get('/', (req, res) => {
    res.send('LLMDriven Co-Op Game server running.');
});

// Add this POST endpoint for the test client
app.post('/example', (req, res) => {
    console.log('[Server] Received POST /example:', req.body);
    res.json({ message: 'POST /example received!', received: req.body });
});

const PORT = process.env.PORT || 3000;
const server = app.listen(PORT, () => {
    console.log(`[Server] Listening on port ${PORT}`);
});

process.on('SIGINT', () => {
    console.log('\n[Server] Caught SIGINT (Ctrl+C), shutting down gracefully...');
    server.close(() => {
        console.log('[Server] Closed out remaining connections.');
        process.exit(0);
    });
});

module.exports = app;
