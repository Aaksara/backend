import { Router } from 'express';
import { addAssignment, getEnrolledAssignments } from '../controllers/assignmentController';
import { authenticateJWT } from '../middleware/auth';
import { checkRole } from '../middleware/roleCheck';

const router = Router();

router.post('/', authenticateJWT, checkRole(['TEACHER']), addAssignment);
router.get('/enrolled', authenticateJWT, checkRole(['STUDENT']), getEnrolledAssignments);

export default router;
