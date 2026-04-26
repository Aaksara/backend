import { Request, Response } from 'express';
import prisma from '../utils/prisma';

interface AuthRequest extends Request {
  user?: {
    id: string;
    email: string;
    role: string;
  };
}

export const createCourse = async (req: AuthRequest, res: Response) => {
  try {
    const { name, description } = req.body;
    const teacherId = req.user?.id;

    if (!teacherId) return res.status(401).json({ message: 'Unauthorized' });

    const course = await prisma.course.create({
      data: {
        name,
        description,
        teacherId,
      },
    });

    res.status(201).json(course);
  } catch (error) {
    res.status(500).json({ message: 'Failed to create course', error });
  }
};

export const getTeacherCourses = async (req: AuthRequest, res: Response) => {
  try {
    const teacherId = req.user?.id;

    const courses = await prisma.course.findMany({
      where: { teacherId },
      include: {
        _count: {
          select: { students: true, assignments: true },
        },
      },
    });

    res.json(courses);
  } catch (error) {
    res.status(500).json({ message: 'Failed to fetch courses', error });
  }
};

export const getAllCourses = async (req: Request, res: Response) => {
  try {
    const courses = await prisma.course.findMany({
      include: { teacher: { select: { name: true, email: true } }, _count: { select: { students: true } } }
    });
    res.json(courses);
  } catch (error) {
    res.status(500).json({ message: 'Failed to fetch courses', error });
  }
};

export const getCourseById = async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const course = await prisma.course.findUnique({
      where: { id },
      include: { teacher: { select: { name: true } }, assignments: true }
    });
    if (!course) return res.status(404).json({ message: 'Course not found' });
    res.json(course);
  } catch (error) {
    res.status(500).json({ message: 'Failed to fetch course', error });
  }
};

export const enrollCourse = async (req: AuthRequest, res: Response) => {
  try {
    const { id } = req.params;
    const studentId = req.user?.id;
    if (!studentId) return res.status(401).json({ message: 'Unauthorized' });

    await prisma.course.update({
      where: { id },
      data: { students: { connect: { id: studentId } } }
    });
    res.json({ message: 'Enrolled successfully' });
  } catch (error) {
    res.status(500).json({ message: 'Failed to enroll in course', error });
  }
};

export const getEnrolledCourses = async (req: AuthRequest, res: Response) => {
  try {
    const studentId = req.user?.id;
    const user = await prisma.user.findUnique({
      where: { id: studentId },
      include: { enrolled: { include: { teacher: { select: { name: true } } } } }
    });
    res.json(user?.enrolled || []);
  } catch (error) {
    res.status(500).json({ message: 'Failed to fetch enrolled courses', error });
  }
};

export const deleteCourse = async (req: AuthRequest, res: Response) => {
  try {
    const { id } = req.params;
    const teacherId = req.user?.id;
    
    const course = await prisma.course.findUnique({ where: { id } });
    if (!course || course.teacherId !== teacherId) {
      return res.status(403).json({ message: 'Forbidden' });
    }

    await prisma.assignment.deleteMany({ where: { courseId: id } });
    await prisma.course.delete({ where: { id } });
    res.json({ message: 'Course deleted successfully' });
  } catch (error) {
    res.status(500).json({ message: 'Failed to delete course', error });
  }
};
