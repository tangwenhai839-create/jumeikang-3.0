import { Controller, Get, Query } from '@nestjs/common';
import { RecordsService } from './records.service';

@Controller('api/records')
export class RecordsController {
  constructor(private readonly recordsService: RecordsService) {}

  // 查询入住记录
  @Get()
  findAll(
    @Query('name') name?: string,
    @Query('phone') phone?: string,
    @Query('roomNumber') roomNumber?: string,
    @Query('startDate') startDate?: string,
    @Query('endDate') endDate?: string,
    @Query('status') status?: string,
    @Query('page') page?: string,
    @Query('pageSize') pageSize?: string,
  ) {
    return this.recordsService.findAll({
      name,
      phone,
      roomNumber,
      startDate,
      endDate,
      status,
      page: page ? Number(page) : undefined,
      pageSize: pageSize ? Number(pageSize) : undefined,
    });
  }
}
