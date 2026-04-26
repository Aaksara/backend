import { Router } from 'express';
import { addAssignment, getEnrolledAssignments, getCourseAssignments, deleteAssignment } from '../controllers/assignmentController';
import { authenticateJWT } from '../middleware/auth';
import { checkRole } from '../middleware/roleCheck';

const router = Router();

router.post('/', authenticateJWT, checkRole(['TEACHER']), addAssignment);
router.get('/enrolled', authenticateJWT, checkRole(['STUDENT']), getEnrolledAssignments);
router.get('/course/:courseId', authenticateJWT, getCourseAssignments);
router.delete('/:id', authenticateJWT, checkRole(['TEACHER']), deleteAssignment);

export default router;
