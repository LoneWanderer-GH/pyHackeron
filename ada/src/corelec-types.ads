with Interfaces;
with Interfaces.C;
with Interfaces.C.Extensions;

package Corelec.Types is
   pragma Preelaborate;

   --subtype U8  is Interfaces.unsigned_short;
   --subtype U16 is Interfaces.Unsigned_16;
   --subtype I32 is Interfaces.Integer_32;
   --subtype U8  is Interfaces.C.unsigned_short;
   subtype U8  is Interfaces.C.Extensions.Unsigned_8;
   subtype U16 is Interfaces.C.Extensions.Unsigned_16;
   subtype I32 is Interfaces.C.int;

   type Frame_Array is array (Natural range 0 .. 16) of U8
     with Convention => C;

   type Decoded_Kind is
     (Kind_Unknown, Kind_65, Kind_69, Kind_77, Kind_83)
     with Convention => C;

   type Frame_Type is record
      Frame_Type_Id : U8 := 0;
      Raw           : Frame_Array := (others => 0);
   end record
   with Convention => C;

   type Decoded_Frame is record
      Kind                               : Decoded_Kind := Kind_Unknown;
      Frame_Type_Id                      : U8 := 0;
      Valid                              : U8 := 0;
      Raw                                : Frame_Array := (others => 0);
      Has_Ph                             : U8 := 0;
      Ph                                 : Interfaces.C.double := 0.0;
      Has_Redox                          : U8 := 0;
      Redox                              : I32 := 0;
      Has_Temp                           : U8 := 0;
      Temp                               : Interfaces.C.double := 0.0;
      Has_Sel                            : U8 := 0;
      Sel                                : Interfaces.C.double := 0.0;
      Has_Ph_Consigne                    : U8 := 0;
      Ph_Consigne                        : Interfaces.C.double := 0.0;
      Has_Err_Max                        : U8 := 0;
      Err_Max                            : Interfaces.C.double := 0.0;
      Has_Err_Min                        : U8 := 0;
      Err_Min                            : Interfaces.C.double := 0.0;
      Has_Redox_Consigne                 : U8 := 0;
      Redox_Consigne                     : I32 := 0;
      Has_Boost_Remaining_Min            : U8 := 0;
      Boost_Remaining_Min                : I32 := 0;
      Has_Current_Electrolyse_Percent    : U8 := 0;
      Current_Electrolyse_Percent        : I32 := 0;
      Has_Inversion_Period_Min           : U8 := 0;
      Inversion_Period_Min               : I32 := 0;
      Has_Shutter_Mode_Electrolyse       : U8 := 0;
      Shutter_Mode_Electrolyse_Percent   : I32 := 0;
      Has_Inversion_Timer_Min            : U8 := 0;
      Inversion_Timer_Min                : I32 := 0;
      Has_Cycle_B_Min                    : U8 := 0;   --  réservé (présent dans corelec_ada.h)
      Cycle_B_Min                        : I32 := 0;
      Alarme                             : U8 := 0;
      Warning                            : U8 := 0;
      Alarm_Rdx                          : U8 := 0;
      Pompe_Moins_Active                 : U8 := 0;
      Regulation_Active                   : U8 := 0;
      Config_Capteur_Sel_Actif           : U8 := 0;  --  frame 77 : raw(13) bit 3
      Pompes_Forcees                     : U8 := 0;
      Boost_Active                       : U8 := 0;
      Flow_Switch                        : U8 := 0;
      Volet_Actif                        : U8 := 0;
      Volet_Force                        : U8 := 0;
      Elx_Fault_Code                     : U8 := 0;  --  frame 65 : raw(12), 0=OK 7=défaut flux 3=transitoire
   end record
   with Convention => C;

   type Connection_State is
     (State_Disconnected, State_Connecting, State_Connected, State_Error)
     with Convention => C;

   subtype Message_Index is Natural range 0 .. 127;
   --  Character est layout-compatible avec C char ; Convention => C préserve la représentation.
   type Message_Buffer is array (Message_Index) of Character
     with Convention => C;

   type Connection_Info is record
      State          : Connection_State := State_Disconnected;
      Message        : Message_Buffer := (others => Character'Val (0));
      Elapsed        : Interfaces.C.unsigned := 0;
      Remaining      : Interfaces.C.unsigned := 0;
      Timeout        : Interfaces.C.unsigned := 0;
      Retry_Count    : Interfaces.C.unsigned := 0;
      Should_Retry   : U8 := 0;
      Stop_Requested : U8 := 0;
   end record
   with Convention => C;
end Corelec.Types;
