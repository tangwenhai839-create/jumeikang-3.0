import { Module } from '@nestjs/common';
import { PrismaModule } from './prisma/prisma.module';
import { RoomsModule } from './modules/rooms/rooms.module';
import { ResidentsModule } from './modules/residents/residents.module';
import { RecordsModule } from './modules/records/records.module';
import { StatsModule } from './modules/stats/stats.module';
import { ImportModule } from './modules/import/import.module';

@Module({
  imports: [
    PrismaModule,
    RoomsModule,
    ResidentsModule,
    RecordsModule,
    StatsModule,
    ImportModule,
  ],
})
export class AppModule {}
