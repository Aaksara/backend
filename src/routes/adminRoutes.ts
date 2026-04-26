import { Router } from 'express';
import { getSystemStats } from '../controllers/adminController';
import { authenticateJWT } from '../middleware/auth';
import { checkRole } from '../middleware/roleCheck';

const router = Router();

router.get('/stats', authenticateJWT, checkRole(['SUPER_ADMIN']), getSystemStats);

export default router;
