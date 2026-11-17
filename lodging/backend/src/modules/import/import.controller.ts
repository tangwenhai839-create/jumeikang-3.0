import {
  Controller,
  Get,
  Post,
  UploadedFile,
  UseInterceptors,
  Res,
  BadRequestException,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import type { Response } from 'express';
import { ImportService } from './import.service';

@Controller('api/import')
export class ImportController {
  constructor(private readonly importService: ImportService) {}

  // 下载房间模板
  @Get('template/rooms')
  async downloadRoomTemplate(@Res() res: Response) {
    return this.importService.downloadRoomTemplate(res);
  }

  // 下载学员模板
  @Get('template/residents')
  async downloadResidentTemplate(@Res() res: Response) {
    return this.importService.downloadResidentTemplate(res);
  }

  // 导入房间
  @Post('rooms')
  @UseInterceptors(
    FileInterceptor('file', {
      limits: { fileSize: 10 * 1024 * 1024 }, // 10MB
      fileFilter: (_req, file, cb) => {
        const okExt = /\.xlsx?$/i.test(file.originalname);
        const okMime = [
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'application/vnd.ms-excel',
          'application/octet-stream',
        ].includes(file.mimetype);
        if (!okExt && !okMime) {
          return cb(new BadRequestException('仅支持 .xlsx / .xls 格式文件'), false);
        }
        cb(null, true);
      },
    }),
  )
  async importRooms(@UploadedFile() file: Express.Multer.File) {
    if (!file) throw new BadRequestException('请上传文件');
    const buffer = file.buffer;
    if (!buffer || buffer.length === 0) {
      throw new BadRequestException('文件内容为空');
    }
    return this.importService.importRooms(buffer);
  }

  // 导入学员
  @Post('residents')
  @UseInterceptors(
    FileInterceptor('file', {
      limits: { fileSize: 10 * 1024 * 1024 },
      fileFilter: (_req, file, cb) => {
        const okExt = /\.xlsx?$/i.test(file.originalname);
        const okMime = [
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'application/vnd.ms-excel',
          'application/octet-stream',
        ].includes(file.mimetype);
        if (!okExt && !okMime) {
          return cb(new BadRequestException('仅支持 .xlsx / .xls 格式文件'), false);
        }
        cb(null, true);
      },
    }),
  )
  async importResidents(@UploadedFile() file: Express.Multer.File) {
    if (!file) throw new BadRequestException('请上传文件');
    const buffer = file.buffer;
    if (!buffer || buffer.length === 0) {
      throw new BadRequestException('文件内容为空');
    }
    return this.importService.importResidents(buffer);
  }
}
