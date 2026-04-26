import { Router } from 'express';
import { getSystemStats, getAllUsers, updateUserRole, deleteUser } from '../controllers/adminController';
import { authenticateJWT } from '../middleware/auth';
import { checkRole } from '../middleware/roleCheck';

const router = Router();

router.get('/stats', authenticateJWT, checkRole(['SUPER_ADMIN']), getSystemStats);
router.get('/users', authenticateJWT, checkRole(['SUPER_ADMIN']), getAllUsers);
router.put('/users/:id/role', authenticateJWT, checkRole(['SUPER_ADMIN']), updateUserRole);
router.delete('/users/:id', authenticateJWT, checkRole(['SUPER_ADMIN']), deleteUser);

export default router;
