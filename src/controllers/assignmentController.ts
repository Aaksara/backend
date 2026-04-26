import { Request, Response } from 'express';
import prisma from '../utils/prisma';

interface AuthRequest extends Request {
  user?: {
    id: string;
    email: string;
    role: string;
  };
}

export const addAssignment = async (req: AuthRequest, res: Response) => {
  try {
    const { title, description, courseId } = req.body;
    const teacherId = req.user?.id;

    // Verify course belongs to teacher
    const course = await prisma.course.findUnique({
      where: { id: courseId },
    });

    if (!course || course.teacherId !== teacherId) {
      return res.status(403).json({ message: 'Forbidden: You do not own this course' });
    }

    const assignment = await prisma.assignment.create({
      data: {
        title,
        description,
        courseId,
      },
    });

    res.status(201).json(assignment);
  } catch (error) {
    res.status(500).json({ message: 'Failed to add assignment', error });
  }
};

export const getEnrolledAssignments = async (req: AuthRequest, res: Response) => {
  try {
    const studentId = req.user?.id;

    const assignments = await prisma.assignment.findMany({
      where: {
        course: {
          students: {
            some: { id: studentId },
          },
        },
      },
      include: {
        course: {
          select: { name: true },
        },
      },
    });

    res.json(assignments);
  } catch (error) {
    res.status(500).json({ message: 'Failed to fetch assignments', error });
  }
};
