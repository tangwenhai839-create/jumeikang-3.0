import { IsString, IsBoolean, IsOptional, IsInt, Min, MaxLength } from 'class-validator';

export class CheckInDto {
  @IsString()
  @MaxLength(50)
  name: string;

  @IsString()
  @MaxLength(20)
  phone: string;

  @IsBoolean()
  isStudent: boolean;

  @IsOptional()
  @IsInt()
  @Min(1)
  campUserId?: number;

  @IsOptional()
  @IsBoolean()
  exclusiveUse?: boolean;

  @IsOptional()
  @IsString()
  @MaxLength(500)
  remark?: string;
}

export class UpdateStayDto {
  @IsInt()
  @Min(1)
  roomId: number;

  @IsBoolean()
  exclusiveUse: boolean;

  @IsOptional()
  @IsString()
  @MaxLength(50)
  name?: string;

  @IsOptional()
  @IsString()
  @MaxLength(20)
  phone?: string;
}
