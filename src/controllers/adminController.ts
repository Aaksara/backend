import { Request, Response } from 'express';
import prisma from '../utils/prisma';

export const getSystemStats = async (req: Request, res: Response) => {
  try {
    const totalUsers = await prisma.user.count();
    const totalCourses = await prisma.course.count();
    const teacherCount = await prisma.user.count({ where: { role: 'TEACHER' } });
    const studentCount = await prisma.user.count({ where: { role: 'STUDENT' } });

    res.json({
      totalUsers,
      totalCourses,
      stats: {
        teachers: teacherCount,
        students: studentCount,
      },
    });
  } catch (error) {
    res.status(500).json({ message: 'Failed to fetch stats', error });
  }
};
