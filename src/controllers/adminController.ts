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

export const getAllUsers = async (req: Request, res: Response) => {
  try {
    const users = await prisma.user.findMany({ select: { id: true, name: true, email: true, role: true, createdAt: true } });
    res.json(users);
  } catch (error) {
    res.status(500).json({ message: 'Failed to fetch users', error });
  }
};

export const updateUserRole = async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const { role } = req.body;
    const user = await prisma.user.update({
      where: { id },
      data: { role }
    });
    res.json({ message: 'User role updated', user: { id: user.id, role: user.role } });
  } catch (error) {
    res.status(500).json({ message: 'Failed to update user role', error });
  }
};

export const deleteUser = async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    await prisma.user.delete({ where: { id } });
    res.json({ message: 'User deleted' });
  } catch (error) {
    res.status(500).json({ message: 'Failed to delete user', error });
  }
};
