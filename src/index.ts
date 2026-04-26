import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import authRoutes from './routes/authRoutes';
import adminRoutes from './routes/adminRoutes';
import courseRoutes from './routes/courseRoutes';
import assignmentRoutes from './routes/assignmentRoutes';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(express.json());

// Routes
app.use('/api/auth', authRoutes);
app.use('/api/admin', adminRoutes);
app.use('/api/courses', courseRoutes);
app.use('/api/assignments', assignmentRoutes);

app.get('/', (req, res) => {
  res.send('EMS PRO Backend is running...');
});

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
