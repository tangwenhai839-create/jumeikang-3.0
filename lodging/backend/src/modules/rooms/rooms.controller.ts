import {
  Controller,
  Get,
  Post,
  Patch,
  Delete,
  Body,
  Param,
  Query,
  ParseIntPipe,
} from '@nestjs/common';
import { RoomsService } from './rooms.service';
import { CreateRoomDto, UpdateRoomDto, BatchCreateRoomDto } from './dto/rooms.dto';

@Controller('api/rooms')
export class RoomsController {
  constructor(private readonly roomsService: RoomsService) {}

  // 获取房间列表（支持筛选）
  @Get()
  findAll(
    @Query('keyword') keyword?: string,
    @Query('roomType') roomType?: string,
    @Query('hasAirConditioner') hasAirConditioner?: string,
    @Query('status') status?: string,
  ) {
    return this.roomsService.findAll({ keyword, roomType, hasAirConditioner, status });
  }

  // 获取房间详情
  @Get(':id')
  findOne(@Param('id', ParseIntPipe) id: number) {
    return this.roomsService.findOne(id);
  }

  // 添加房间
  @Post()
  create(@Body() dto: CreateRoomDto) {
    return this.roomsService.create(dto);
  }

  // 批量创建房间
  @Post('batch')
  batchCreate(@Body() dto: BatchCreateRoomDto) {
    return this.roomsService.batchCreate(dto);
  }

  // 编辑房间
  @Patch(':id')
  update(@Param('id', ParseIntPipe) id: number, @Body() dto: UpdateRoomDto) {
    return this.roomsService.update(id, dto);
  }

  // 删除房间
  @Delete(':id')
  remove(@Param('id', ParseIntPipe) id: number) {
    return this.roomsService.remove(id);
  }
}
