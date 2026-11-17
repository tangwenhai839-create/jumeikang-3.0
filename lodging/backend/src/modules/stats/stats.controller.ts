import { Controller, Get } from '@nestjs/common';
import { StatsService } from './stats.service';

@Controller('api/stats')
export class StatsController {
  constructor(private readonly statsService: StatsService) {}

  // 获取数据统计
  @Get()
  getStats() {
    return this.statsService.getStats();
  }
}
