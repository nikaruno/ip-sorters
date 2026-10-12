library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

package typedef is
  type vector_vector is array (NATURAL range <>) of std_logic_vector(7 downto 0);
end;

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.STD_LOGIC_unsigned.ALL;
use work.typedef.all;

entity merge_clk is
  port ( 
    clk : in std_logic;
    start : in std_logic;
    left_vector : in vector_vector(0 to 2);
    right_vector : in vector_vector(0 to 2);
    merged_vector : out vector_vector(0 to 5);
    done : out std_logic
  );
end merge_clk;

architecture Behavioral of merge_clk is

begin

  process(clk)
    variable go : std_logic := '0';
    variable k : natural := 0;
    variable i : natural := 0;
    variable j : natural := 0;
  begin
    if(go = '1') then
      if(k < 5) then
        if(i>2) then
          merged_vector(k) <= right_vector(j);
          j := j + 1;
        elsif(j>2) then
          merged_vector(k) <= left_vector(i);
          i := i + 1;
        elsif(left_vector(i) < right_vector(j)) then
          merged_vector(k) <= left_vector(i);
          i := i + 1; 
        else
          merged_vector(k) <= right_vector(j);
          j := j + 1;
        end if;
        k := k + 1;
        done <= '0';
      else
        go := '0';
        done <= '1';
      end if;
    else
      go := start;
      i := 0;
      j := 0;
      k := 0;
      done <= '0';
    end if;
  end process;

end Behavioral;
