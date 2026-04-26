import { Router } from 'express';
import { createCourse, getTeacherCourses, getAllCourses, getCourseById, enrollCourse, getEnrolledCourses, deleteCourse } from '../controllers/courseController';
import { authenticateJWT } from '../middleware/auth';
import { checkRole } from '../middleware/roleCheck';

const router = Router();

router.post('/', authenticateJWT, checkRole(['TEACHER']), createCourse);
router.get('/', authenticateJWT, getAllCourses);
router.get('/my-courses', authenticateJWT, checkRole(['TEACHER']), getTeacherCourses);
router.get('/enrolled', authenticateJWT, checkRole(['STUDENT']), getEnrolledCourses);
router.get('/:id', authenticateJWT, getCourseById);
router.post('/:id/enroll', authenticateJWT, checkRole(['STUDENT']), enrollCourse);
router.delete('/:id', authenticateJWT, checkRole(['TEACHER']), deleteCourse);

export default router;
