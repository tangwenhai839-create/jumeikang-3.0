import { Controller, Get, Post, Patch, Param, Body, ParseIntPipe } from '@nestjs/common';
import { ResidentsService } from './residents.service';
import { CheckInDto, UpdateStayDto } from './dto/residents.dto';

@Controller('api/rooms')
export class ResidentsController {
  constructor(private readonly residentsService: ResidentsService) {}

  // 查询训练营学员当前住宿
  @Get('camp-resident/:campUserId')
  findByCampUser(@Param('campUserId', ParseIntPipe) campUserId: number) {
    return this.residentsService.findByCampUser(campUserId);
  }

  // 换房或修改“整间独住”状态
  @Patch('resident/:residentId/stay')
  updateStay(
    @Param('residentId', ParseIntPipe) residentId: number,
    @Body() dto: UpdateStayDto,
  ) {
    return this.residentsService.updateStay(residentId, dto);
  }

  // 办理入住
  @Post(':id/check-in')
  checkIn(@Param('id', ParseIntPipe) id: number, @Body() dto: CheckInDto) {
    return this.residentsService.checkIn(id, dto);
  }

  // 办理退房
  @Post(':id/check-out/:residentId')
  checkOut(
    @Param('id', ParseIntPipe) id: number,
    @Param('residentId', ParseIntPipe) residentId: number,
  ) {
    return this.residentsService.checkOut(id, residentId);
  }
}
