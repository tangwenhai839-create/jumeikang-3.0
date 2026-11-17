import { NestFactory } from '@nestjs/core';
import { ValidationPipe, Logger } from '@nestjs/common';
import { AppModule } from './app.module';
import { AllExceptionsFilter } from './common/all-exceptions.filter';

async function bootstrap() {
  const logger = new Logger('Bootstrap');
  const app = await NestFactory.create(AppModule);

  // 全局前缀已在 Controller 中通过 @Controller('api/...') 设置
  app.enableCors({
    origin: true,
    credentials: true,
  });

  // 全局 DTO 校验管道
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      transform: true,
      forbidNonWhitelisted: false,
    }),
  );

  // 全局异常过滤器
  app.useGlobalFilters(new AllExceptionsFilter());

  const port = process.env.PORT ? Number(process.env.PORT) : 3000;
  await app.listen(port, process.env.HOST || '127.0.0.1');
  logger.log(`后端服务已启动: http://localhost:${port}`);
  logger.log(`API 根路径: http://localhost:${port}/api`);
}
bootstrap();
