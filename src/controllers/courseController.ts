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
