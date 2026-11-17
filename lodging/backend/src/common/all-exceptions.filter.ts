import {
  ExceptionFilter,
  Catch,
  ArgumentsHost,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import { Request, Response } from 'express';

@Catch()
export class AllExceptionsFilter implements ExceptionFilter {
  private readonly logger = new Logger(AllExceptionsFilter.name);

  catch(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();
    const request = ctx.getRequest<Request>();

    let status = HttpStatus.INTERNAL_SERVER_ERROR;
    let message = '服务器内部错误';

    if (exception instanceof HttpException) {
      status = exception.getStatus();
      const res = exception.getResponse();
      if (typeof res === 'string') {
        message = res;
      } else if (typeof res === 'object' && res !== null) {
        const r = res as any;
        message = Array.isArray(r.message) ? r.message.join('; ') : r.message || message;
      }
    } else if (exception instanceof Error) {
      message = exception.message;
      this.logger.error(exception.stack);
    }

    // Prisma 常见错误转友好提示
    const errMsg = (exception as any)?.message || '';
    if (errMsg.includes('Unique constraint')) {
      status = HttpStatus.BAD_REQUEST;
      message = '数据重复，请检查唯一字段（如房间号）';
    }

    response.status(status).json({
      code: status,
      message,
      path: request.url,
      timestamp: new Date().toISOString(),
    });
  }
}
