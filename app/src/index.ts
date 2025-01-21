import express from 'express';
import pool from './db';          // Postgres pool
import esClient from './esClient'; // Elasticsearch client

const app = express();
app.use(express.json());

// Health check
app.get('/health', async (_req, res) => {
  try {
    const dbTime = await pool.query('SELECT NOW()');
    const esInfo = await esClient.info();
    res.json({
      status: 'ok',
      dbTime: dbTime.rows[0].now,
      esVersion: esInfo.version,
    });
  } catch (error: any) {
    console.error('Error in /health:', error);
    res.status(500).json({ error: error.message });
  }
});

// Example endpoint: get all rows from a table
app.get('/items', async (_req, res) => {
  try {
    const { rows } = await pool.query('SELECT * FROM items');
    res.json(rows);
  } catch (error: any) {
    console.error('Error in /items:', error);
    res.status(500).json({ error: error.message });
  }
});

// Example endpoint: search documents in Elasticsearch
app.get('/search', async (req, res) => {
  const query: string = req.query.q as string ?? '';
  try {
    const result = await esClient.search({
      index: 'my_index',
      query: {
        match: {
          message: query,
        },
      },
    });
    res.json(result.hits.hits);
  } catch (error: any) {
    console.error('Error in /search:', error);
    res.status(500).json({ error: error.message });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
