import { Router } from 'express';
import { createCourse, getTeacherCourses } from '../controllers/courseController';
import { authenticateJWT } from '../middleware/auth';
import { checkRole } from '../middleware/roleCheck';

const router = Router();

router.post('/', authenticateJWT, checkRole(['TEACHER']), createCourse);
router.get('/my-courses', authenticateJWT, checkRole(['TEACHER']), getTeacherCourses);

export default router;
